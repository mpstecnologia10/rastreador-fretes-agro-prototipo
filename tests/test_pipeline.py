import hashlib
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pipeline.adapters.authorized import AuthorizedFile
from pipeline.build import ROOT, demo, read, run, sources, write
from pipeline.domain import Cities, cnpj_ok, compatibility, instant, normalize, phone, safe_url, temporal
from pipeline.ranking import merge, opportunities
from pipeline.routing import Router

NOW=instant("2026-11-22T15:00:00Z")

def data(fmt="authorized_json"):
    p={"id":"feed-company","file":"offers.json" if fmt.endswith("json") else "offers.csv","adapter":fmt,
       "permission_ref":"fixture-not-authorization","permission_until":"2027-01-01T00:00:00Z",
       "publisher_url":"https://empresa.example","company":"Empresa QA","publish":False}
    r=dict(next(demo(NOW))[1])
    r.update(url="https://empresa.example/oferta/1",contato_empresarial="(66) 99999-9999",cnpj="11.222.333/0001-81")
    return p,r

class Domain(unittest.TestCase):
    def setUp(self):
        self.cities=Cities(read(ROOT/"data/hubs.json"))

    def test_ibge_alias(self):
        self.assertEqual(self.cities.resolve("Primavera Leste/MT")["ibge"],"5107040")
        self.assertEqual(self.cities.resolve("Rondonopolis MT")["ibge"],"5107602")
        self.assertEqual(self.cities.resolve("Miritituba")["ibge"],"1503606")

    def test_ambiguous_city(self):
        c=Cities(read(ROOT/"data/hubs.json"),[{"id":5110000,"nome":"Teste"},{"id":5210000,"nome":"Teste"}])
        with self.assertRaises(ValueError): c.resolve("Teste")
        self.assertEqual(c.resolve("Teste/GO")["ibge"],"5210000")

    def test_original_price_and_rounding(self):
        p,r=data(); r["valor"]="1.234,56"
        n=normalize(r,p,NOW,self.cities)
        self.assertEqual(n["preco_original"],"1.234,56")
        self.assertEqual(n["valor_centavos"],123456)
        self.assertEqual(n["valor_50t_centavos"],6172800)
        r.update(tipo_valor="fechado")
        self.assertIsNone(normalize(r,p,NOW,self.cities)["valor_50t_centavos"])

    def test_weight_and_unproved_rate(self):
        p,r=data();r.update(peso_t=48)
        self.assertEqual(normalize(r,p,NOW,self.cities)["peso_t"],48)
        self.assertIsNone(normalize(r,p,NOW,self.cities)["valor_50t_centavos"])
        r.update(peso_t=52)
        self.assertEqual(normalize(r,p,NOW,self.cities)["compatibilidade"],"NAO_CONFIRMADA")

    def test_business_contact_opt_in(self):
        p,r=data()
        self.assertIsNone(normalize(r,p,NOW,self.cities)["contato_empresarial"])
        p["publish_business_contact"]=True
        self.assertEqual(normalize(r,p,NOW,self.cities)["contato_empresarial"],"+5566999999999")
        self.assertIsNone(phone("123"))

    def test_cnpj_and_rntrc_unknown(self):
        p,r=data()
        n=normalize(r,p,NOW,self.cities)
        self.assertTrue(n["cnpj"]["digitos_validos"])
        self.assertFalse(cnpj_ok("00000000000000"))
        self.assertTrue(cnpj_ok("12.ABC.345/01DE-35"))
        self.assertFalse(cnpj_ok("12.ABC.345/01DE-99"))
        self.assertEqual(n["cnpj"]["situacao"],"NAO_CONSULTADA")
        self.assertEqual(n["rntrc"]["situacao"],"CONSULTA_MANUAL")

    def test_link_unsafe(self):
        self.assertIsNone(safe_url("javascript:alert(1)"))
        self.assertIsNone(safe_url("https://user@empresa.example/x"))
        self.assertEqual(safe_url("https://empresa.example/x?token=private"),"https://empresa.example/x")
        p,r=data()
        with self.assertRaises(ValueError): normalize(dict(r,url="https://other.example/x"),p,NOW,self.cities)

    def test_compatibility(self):
        self.assertEqual(compatibility("Graneleiro","Rodotrem",50,"x")[0],"PROVAVEL")
        self.assertEqual(compatibility("Tanque","Rodotrem",50,"x")[0],"INCOMPATIVEL")
        p,r=data()
        r["conjunto_25m_50t_confirmado"]="sim"
        self.assertEqual(normalize(r,p,NOW,self.cities)["compatibilidade"],"PROVAVEL")
        p["allow_equipment_confirmation"]=True
        self.assertEqual(normalize(r,p,NOW,self.cities)["compatibilidade"],"CONFIRMADA")

    def test_age_and_expiration(self):
        self.assertEqual(temporal(NOW-timedelta(hours=36),None,NOW),"RECENTE")
        self.assertEqual(temporal(NOW-timedelta(hours=73),None,NOW),"POSSIVELMENTE_EXPIRADA")
        self.assertEqual(temporal(NOW-timedelta(hours=2),NOW,NOW),"EXPIRADA")

    def test_dedup_and_price_history(self):
        state={}
        rows=[normalize(r,p,NOW,self.cities) for p,r in demo(NOW)]
        result=merge(rows,state,NOW)
        self.assertEqual(len(result),9)
        match=next(x for x in result if x["fontes_distintas"]==2)
        self.assertEqual(len(match["historico_valores"]),2)
        self.assertNotIn("_identity",match)
        later=merge([rows[1]],state,NOW+timedelta(hours=1))[0]
        self.assertEqual(later["id"],match["id"])
        self.assertEqual(later["primeira_vez_vista"],match["primeira_vez_vista"])

    def test_no_duplicate_only_by_route(self):
        p,r=data();q=dict(p,id="feed-other")
        rows=[normalize(dict(r,referencia_embarcador=""),x,NOW,self.cities) for x in (p,q)]
        self.assertEqual(len(merge(rows,{},NOW)),2)

    def test_route_cache_direction_budget_and_fallback(self):
        a,b=map(self.cities.resolve,("Primavera Leste","Campo Verde"))
        cache={}
        route=Router(NOW,cache,lambda a,b:160,1)
        self.assertEqual(route.route(a,b)["metodo"],"OSRM_ESTIMADO")
        self.assertEqual(Router(NOW,cache).route(a,b)["km"],160)
        self.assertEqual(route.route(b,a)["metodo"],"GEODESICA")
        def fails(a,b): raise OSError("offline")
        self.assertEqual(Router(NOW,{},fails,1).route(a,b)["metodo"],"GEODESICA")
        self.assertEqual(Router(NOW+timedelta(days=31),cache).route(a,b)["metodo"],"GEODESICA")

    def test_ranking_approximation_has_no_per_km(self):
        rows=merge([normalize(r,p,NOW,self.cities) for p,r in demo(NOW)],{},NOW)
        opp=opportunities(self.cities.resolve("Primavera Leste"),rows,Router(NOW,{}))
        self.assertTrue(opp)
        self.assertTrue(all(o["rs_km_operacional_centavos"] is None for o in opp))
        self.assertEqual(opp[0]["ranking"]["pontos"],round(sum(opp[0]["ranking"]["motivos"].values()),1))

class Export(unittest.TestCase):
    def args(self,root,**overrides):
        return SimpleNamespace(**dict({"now":NOW.isoformat(),"demo":False,"public":False,"osrm":False,"refresh_ibge":False,
            "inputs":root/"inputs","cache":root/"cache","output":root/"dist"},**overrides))

    def add(self,root,fmt="authorized_json"):
        p,r=data(fmt); inputs=root/"inputs";inputs.mkdir(exist_ok=True)
        if fmt.endswith("json"):
            write(inputs/p["file"],{"schema_version":1,"cargas":[r]})
        else:
            import csv
            with (inputs/p["file"]).open("w",encoding="utf-8") as h:
                w=csv.DictWriter(h,fieldnames=list(r));w.writeheader();w.writerow(r)
        p["sha256"]=hashlib.sha256((inputs/p["file"]).read_bytes()).hexdigest()
        return p

    def test_authorized_formats(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path)
            for fmt in ("authorized_csv","authorized_json"):
                p=self.add(root,fmt);self.assertEqual(len(AuthorizedFile(root/"inputs",p,NOW).healthcheck()),1)

    def test_runtime_isolation_when_one_source_fails(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path);p=self.add(root)
            write(root/"inputs/manifest.json",{"schema_version":1,"feeds":[dict(p,id="feed-failed",sha256="0"),p]})
            a=self.args(root)
            m=run(a)
            self.assertEqual((m["reais"],m["fontes_falhando"]),(1,1))
            self.assertEqual(run(self.args(root,public=True))["reais"],0)
            s=read(a.output/"data/sources_registry.json")
            self.assertNotIn("feed-company",[x["id"] for x in s["fontes"]])
            self.assertFalse((a.output/"data/manual_authorized").exists())

    def test_expired_wrong_hash_and_schema_rejected(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path);p=self.add(root)
            for overrides in ({"permission_until":"2025-01-01T00:00:00Z"},{"sha256":"bad"},{"file":"../offers.json"}):
                with self.assertRaises(ValueError): AuthorizedFile(root/"inputs",dict(p,**overrides),NOW).healthcheck()
            with self.assertRaises(ValueError):
                AuthorizedFile(root/"inputs",p,NOW).parse(b'{"schema_version":2,"cargas":[]}')

    def test_public_real_freight_checks_review_and_total_floor(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path)
            p,r=data()
            inputs=root/"inputs"
            for reviewed,floor,expected in ((False,300000,0),(True,600000,0),(True,525000,1)):
                write(inputs/p["file"],{"schema_version":1,"cargas":[dict(r,piso_antt_centavos=floor)]})
                write(inputs/"manifest.json",{"schema_version":1,"feeds":[dict(p,publish=True,public_antt_reviewed=reviewed,
                    sha256=hashlib.sha256((inputs/p["file"]).read_bytes()).hexdigest())]})
                self.assertEqual(run(self.args(root,public=True))["reais"],expected)

    def test_demo_contract_and_public_catalog(self):
        with tempfile.TemporaryDirectory() as path:
            a=self.args(Path(path),demo=True,public=True)
            m=run(a)
            self.assertEqual((m["bruto"],m["total"],m["reais"]),(10,9,0))
            for x in [a.output/"data/cargas.json",a.output/"data/sources_registry.json",*(a.output/"data/oportunidades").glob("*.json")]:
                data=read(x)
                self.assertEqual((data["schema_version"],data["snapshot_id"],data["modo"]),(1,m["snapshot_id"],"DEMO"))
            fretebras=next(r for r in sources({}) if r["id"]=="fretebras")
            self.assertEqual(fretebras["classificacao"],"LINK_ONLY")

    def test_ibge_outage_keeps_hubs(self):
        with tempfile.TemporaryDirectory() as path,patch("pipeline.build.download",side_effect=OSError):
            m=run(self.args(Path(path),refresh_ibge=True))
            self.assertEqual((len(m["hubs"]),m["fontes_falhando"]),(16,1))
