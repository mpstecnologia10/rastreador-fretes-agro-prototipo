import json
import unittest
from datetime import date
from pathlib import Path

from pipeline.build import ROOT, sources
from pipeline.capture import analyze, parse
from pipeline.domain import Cities

TODAY=date(2026,11,22)
CITIES=Cities(json.loads((ROOT/"data/hubs.json").read_text()),[
    {"id":1506104,"nome":"Primavera"}, {"id":3509502,"nome":"Campinas"}, {"id":3548500,"nome":"Santos"}])

class CaptureTest(unittest.TestCase):
    def test_reference_offer(self):
        data=parse("Primavera do Leste MT x Santos SP\nsoja\nrodotrem graneleiro\n50 ton\n470/t\ncarrega amanhã",CITIES,TODAY)
        self.assertEqual([data[k]["valor"] for k in ("origem","destino","produto","configuracao","peso_t","valor","carregamento")],
                         ["5107040","3548500","Soja","Rodotrem","50","470","2026-11-23"])
        result=analyze({k:f["valor"] for k,f in data.items()},CITIES,TODAY)
        self.assertEqual(result["total_centavos"],2350000)
        self.assertEqual(result["compatibilidade"],"PROVAVEL")
        self.assertIsNone(result["rs_km_centavos"])
        self.assertIsNone(result["piso_diferenca_centavos"])

    def test_routes_and_ambiguity(self):
        for s in ("Origem: Primavera-MT Destino: Santos/SP","Primavera-MT > Santos",
                  "Primavera-MT/Santos","🚚 Primavera-MT para Santos","Origem: Primavera-MT\nDestino: Santos"):
            with self.subTest(s=s):
                r=parse(s,CITIES,TODAY)
                self.assertEqual(r["origem"]["valor"],"5107040")
                self.assertEqual(r["origem"]["confianca"],"PROVÁVEL")
                self.assertEqual(r["destino"]["valor"],"3548500")
        r=parse("Primavera x Santos / Campinas",CITIES,TODAY)
        self.assertTrue(all(r[k]["confianca"]=="INCERTO" and len(r[k]["opcoes"])==2 for k in ("origem","destino")))
        r=parse("Primavera-MT x Santos/SP\nRondonópolis-MT x Campinas/SP",CITIES,TODAY)
        self.assertTrue(all(r[k]["confianca"]=="INCERTO" for k in ("origem","destino")))

    def test_price_is_fail_closed(self):
        for s in ("frete 470","R$ 470 ton","470 ton","R$ 470"):
            r=parse(s,CITIES,TODAY)
            self.assertEqual(r["valor"]["confianca"],"INCERTO")
            self.assertIsNone(r["tipo_precificacao"]["valor"])
        for s, kind, value in (("R$ 23.500 fechado","fechado","23500"),("470 a tonelada","por_tonelada","470"),
                               ("470,50 por ton","por_tonelada","470.50"),("R$ 470/t","por_tonelada","470")):
            r=parse(s,CITIES,TODAY)
            self.assertEqual((r["tipo_precificacao"]["valor"],r["valor"]["valor"]),(kind,value))
        self.assertEqual(parse("Soja 48.000 kg",CITIES,TODAY)["peso_t"]["valor"],"48")
        self.assertEqual(parse("sem preço",CITIES,TODAY)["valor"]["confianca"],"AUSENTE")

    def test_company_contact_and_products(self):
        r=parse("🚛 farelo de soja | carreta LS graneleiro 9 eixos\nEmpresa: Fictícia\nCNPJ: 12.ABC.345/01DE-35\nWhatsApp: (66) 99999-9999\nObs: confirmar fila",CITIES,TODAY)
        self.assertEqual([r[k]["valor"] for k in ("produto","configuracao","empresa","cnpj","telefone","observacoes")],
                         ["Farelo","Carreta LS","Fictícia","12.ABC.345/01DE-35","+5566999999999","confirmar fila"])
        self.assertEqual(r["cnpj"]["confianca"],"CONFIRMADO")
        self.assertEqual(parse("CNPJ 00.000.000/0000-00",CITIES,TODAY)["cnpj"]["confianca"],"INCERTO")

    def test_references_only_comparable(self):
        args={"origem":"5107040","destino":"3548500","produto":"Soja","valor":"470","peso_t":"50",
              "tipo_precificacao":"por_tonelada","km_rodoviario":"2200","mercado_valor":"445",
              "mercado_data":"2026-11-20","mercado_rota":True,"mercado_unidade":"por_tonelada",
              "antt_valor":"20000","antt_operacao":True}
        r=analyze(args,CITIES,TODAY)
        self.assertEqual((r["mercado_diferenca_pct"],r["piso_diferenca_centavos"],r["rs_km_centavos"]),(5.6,350000,1068))
        self.assertIsNone(analyze(dict(args,mercado_unidade="fechado"),CITIES,TODAY)["mercado_diferenca_pct"])
        self.assertIsNone(analyze(dict(args,km_rodoviario="1"),CITIES,TODAY)["piso_diferenca_centavos"])
        self.assertIsNone(analyze(dict(args,mercado_data="2026-10-01"),CITIES,TODAY)["mercado_diferenca_pct"])

    def test_registry_not_permission(self):
        items={i["id"]:i for i in sources({})}
        self.assertEqual(items["fretebras"]["acquisition_mode"],"FEDERATED_SEARCH")
        self.assertEqual(items["fretebras"]["classificacao"],"LINK_ONLY")
        self.assertEqual(items["sifreca"]["acquisition_mode"],"CONTEXT_SOURCE")
        self.assertFalse(any(s["can_republish"] for s in items.values()))
        self.assertFalse(any(s["can_ingest"] for k,s in items.items() if k!="ibge"))
