import argparse
import csv
import json
import re
import shutil
import tempfile
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic,sleep
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .adapters.authorized import AuthorizedFile
from .domain import SCHEMA, STATES, Cities, cents, decimal, digest, instant, iso, normalize, safe_url, text
from .ranking import merge, opportunities
from .routing import Router

ROOT=Path(__file__).resolve().parents[1]
AGENT="RastreadorFretesAgroPrototype/1.0"
IBGE="https://servicodados.ibge.gov.br/api/v1/localidades/municipios"

def read(path,default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if default is not None: return default
        raise

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, encoding="utf-8", delete=False) as t:
        json.dump(data,t,ensure_ascii=False,separators=(",",":"),allow_nan=False)
        t.write("\n")
    Path(t.name).replace(path)

def download(url):
    with urlopen(Request(url, headers={"User-Agent":AGENT}), timeout=9) as r:
        if urlsplit(r.geturl()).hostname!=urlsplit(url).hostname:
            raise ValueError("redirecionamento entre hosts")
        raw=r.read(10_000_001)
        if len(raw)>10_000_000: raise ValueError("resposta muito grande")
        return json.loads(raw)

def demo(now):
    specs=[
      ("demo-a","AG-1","1","5107040","3548500","Soja","Rodotrem",50,"105","por_tonelada",3),
      ("demo-b","AG-1","2","5107040","3548500","Soja","Rodotrem",50,"110","por_tonelada",4),
      ("demo-a","AG-2","3","5102678","4118204","Milho","Bitrem 9 eixos",50,"5500","fechado",9),
      ("demo-b","AG-3","4","5107602","3170206","Fertilizantes","Rodotrem",48,"98","por_tonelada",21),
      ("demo-a","AG-4","5","5107925","5107602","Soja","Rodotrem",50,"","",22),
      ("demo-b","AG-5","6","4118204","5003702","DDGS","Rodotrem",50,"","",62),
      ("demo-b","AG-6","7","5218805","5106224","Milho","Rodotrem",50,"","",5),
      ("demo-a","AG-7","8","1503606","5107909","Soja","Rodotrem",50,"","",10),
      ("demo-a","AG-8","9","4315602","4118204","Farelo","Rodotrem",50,"","",3),
      ("demo-b","AG-9","10","5003702","4118204","Milho","Rodotrem",50,"","",4),
    ]
    for source,ref,ext,o,d,product,config,w,val,kind,age in specs:
        yield {"id":source,"company":"Empresa fictícia","synthetic":True}, {
          "id_oferta":ext,"referencia_embarcador":ref,"origem":o,"destino":d,"produto":product,
          "carroceria":"Graneleiro","configuracao":config,"peso_t":w,"valor":val,"tipo_valor":kind,
          "publicado_em":iso(now-timedelta(hours=age)),"validade":iso(now+timedelta(hours=24)),
        }

def sources(audit):
    raw=csv.DictReader((ROOT/"data/candidates.csv").read_text(encoding="utf-8").splitlines())
    extra=read(ROOT/"data/hybrid_sources.json")
    return [{
      **r,"estados":r["estados"].split(),"coleta_automatica":r["id"]=="ibge","login":r["tipo"]=="login",
      "captcha":"não verificado","termos_revisados":r["id"] in ("fretebras","trizy"),
      "prioridade":1 if r["id"] in {"fiagril","amaggi","cs","1500"} else 2,
      "ultima_tentativa":None,"ultimo_sucesso":None,"encontradas":0,"aproveitadas":0,"status":"NÃO COLETADA","erro":None,
      "descoberta":audit.get(r["id"],{}),
      **source_mode("OFFICIAL_VALIDATION" if r["classificacao"]=="OFFICIAL_VALIDATION" else "PUBLISHER_INPUT",
                    requires_login=True if r["tipo"]=="login" else None, can_ingest=r["id"]=="ibge"),
      **extra.get(r["id"],{}),
    } for r in raw]

def source_mode(mode, **fields):
    return dict({"acquisition_mode":mode,"search_url_template":None,"supports_origin_param":False,
                 "supports_destination_param":False,"supports_vehicle_param":False,"requires_login":None,
                 "can_republish":False,"can_ingest":False,"terms_checked_at":None,"terms_notes":None},**fields)

def run(args):
    then=monotonic()
    now=instant(args.now) if args.now else datetime.now(UTC)
    state_path=args.cache/("demo.json" if args.demo else ("public.json" if args.public else "piloto.json"))
    state=read(state_path,{})
    report=sources(read(ROOT/"data/source_audit.json",{}))
    city_file=args.cache/"ibge.json"
    geo=read(city_file,{"municipios":[]})
    ibge=next(r for r in report if r["id"]=="ibge")
    if args.refresh_ibge:
        ibge["ultima_tentativa"]=iso(now)
        try:
            new=download(IBGE)
            if not isinstance(new,list) or len(new)<5000 or not all("id" in r and "nome" in r for r in new): raise ValueError("catálogo inválido")
            geo={"municipios":new,"at":iso(now)}
            write(city_file,geo)
            ibge["status"]="OK"
        except (OSError,ValueError,TypeError):
            ibge.update(status="FALHA; USANDO CACHE OU HUBS",erro="Catálogo oficial indisponível")
    ibge.update(ultimo_sucesso=geo.get("at"),encontradas=len(geo["municipios"]),
                aproveitadas=sum(str(r["id"])[:2] in STATES for r in geo["municipios"]))
    cities=Cities(read(ROOT/"data/hubs.json"),geo["municipios"])
    raw_count=0
    real=[]
    rejected=0
    if args.demo:
        for policy,row in demo(now):
            real.append(normalize(row,policy,now,cities))
            raw_count+=1
    else:
        manifest=read(args.inputs/"manifest.json",{"schema_version":1,"feeds":[]})
        if not isinstance(manifest,dict) or manifest.get("schema_version")!=1 or not isinstance(manifest.get("feeds"),list):
            raise ValueError("manifesto de entrada inválido")
        existing={r["id"] for r in report}
        for policy in manifest["feeds"]:
            if not isinstance(policy,dict): raise ValueError("política de feed inválida")
            if args.public and policy.get("publish") is not True:
                continue
            source=policy.get("id")
            if not isinstance(source,str) or not re.fullmatch(r"feed-[a-z0-9-]{2,50}",source) or source in existing or policy.get("synthetic"):
                raise ValueError("identificador de feed inválido ou repetido")
            existing.add(source)
            entry={"id":source,"nome":text(policy.get("company")),"empresa":text(policy.get("company")),
                   "categoria":"fornecedor","url":safe_url(policy.get("publisher_url")),"estados":[],
                   "tipo":policy.get("adapter"),"classificacao":"AUTHORIZED_FEED","coleta_automatica":False,
                   "login":False,"captcha":False,"termos_revisados":bool(policy.get("permission_ref")),
                   "prioridade":1,"ultima_tentativa":iso(now),"ultimo_sucesso":state.setdefault("success",{}).get(source),
                   "encontradas":0,"aproveitadas":0,"status":"OK","erro":None,
                   **source_mode("PUBLISHER_INPUT",requires_login=False,
                                 terms_notes="Escopo do arquivo aprovado separadamente.")}
            a=AuthorizedFile(args.inputs,policy,now,args.public)
            try: rows=a.healthcheck()
            except (OSError,ValueError,TypeError,KeyError):
                entry.update(status="FALHA",erro="Arquivo ou autorização não pôde ser validado.")
                if not args.public:
                    report.append(entry)
                continue
            report.append(entry)
            entry.update(can_ingest=True,can_republish=policy.get("publish") is True)
            raw_count+=len(rows)
            entry["encontradas"]=len(rows)
            for row in rows:
                try:
                    normalized=a.normalize(row,cities)
                    if args.public:
                        floor=row.get("piso_antt_centavos")
                        if isinstance(floor,str) and re.fullmatch(r"[0-9]{1,12}",floor.strip()):
                            floor=int(floor)
                        offered=normalized["valor_centavos"]
                        if normalized["tipo_precificacao"]=="por_tonelada":
                            offered=cents(decimal(row["valor"])*decimal(row["peso_t"])) if row.get("peso_t") else None
                        if (policy.get("public_antt_reviewed") is not True or type(floor) is not int
                            or floor<=0 or offered is None or offered<floor):
                            raise ValueError("validação de preço/piso para publicação não confirmada")
                    real.append(normalized)
                except (ValueError,TypeError,KeyError,OverflowError): rejected+=1
                else: entry["aproveitadas"]+=1
            if entry["aproveitadas"]==len(rows):
                entry["ultimo_sucesso"]=state["success"][source]=iso(now)
            else:
                entry.update(status="PARCIAL" if entry["aproveitadas"] else "FALHA",erro="Há linhas rejeitadas pela validação.")
    loads=merge(real,state,now)
    snapshot=digest(("demo" if args.demo else "real")+now.isoformat()+json.dumps([loads,report],sort_keys=True))
    shared={"schema_version":SCHEMA,"snapshot_id":snapshot,"modo":"DEMO" if args.demo else "REAL"}
    data=args.output/"data"
    routing=Router(now,state.setdefault("routes",{}) if args.osrm else {},
                   fetch=osrm if args.osrm else None,limit=3 if args.osrm else 0)
    hubs=[cities.ids[x] for x in cities.hubs]
    for hub in hubs:
        write(data/"oportunidades"/(hub["ibge"]+".json"),{**shared,"municipio":hub,"oportunidades":opportunities(hub,loads,routing)})
    write(data/"cargas.json",{**shared,"cargas":loads})
    write(data/"sources_registry.json",{**shared,"fontes":report})
    geographic=read(ROOT/"data/geo_entities.json",{})
    for name in ("geo_entities.json","company_platform_map.json","route_context.json"):
        if (ROOT/"data"/name).is_file(): shutil.copy2(ROOT/"data"/name,data/name)
    write(data/"municipios.json",{"hubs":read(ROOT/"data/hubs.json"),
                                "official":[{"id":c["ibge"],"nome":c["nome"]} for c in cities.ids.values()]})
    write(data/"meta.json",{**shared,"atualizado_em":iso(now),"duracao_s":round(monotonic()-then,3),
        "bruto":raw_count,"valido":len(real),"rejeitadas":rejected,"duplicatas":len(real)-len(loads),"total":len(loads),
        "reais":sum(not r["sintetico"] for r in loads),"com_preco":sum(r["valor_centavos"] is not None for r in loads),
        "sem_preco":sum(r["valor_centavos"] is None for r in loads),"compativeis":sum(r["compatibilidade"] in ("PROVAVEL","CONFIRMADA") for r in loads),
        "por_estado":dict(Counter(r["origem"]["uf"] for r in loads)),"por_produto":dict(Counter(r["produto"] for r in loads)),
        "fontes_ativas":sum(r["status"]=="OK" and r["aproveitadas"]>0 and r["classificacao"] in ("AUTHORIZED_FEED","INGEST") for r in report),
        "fontes_falhando":sum(r["status"].startswith("FALHA") for r in report),
        **{key:sum(r["acquisition_mode"]==mode for r in report) for key,mode in {
            "open_ingest_sources":"OPEN_INGEST","federated_sources":"FEDERATED_SEARCH",
            "context_sources":"CONTEXT_SOURCE","restricted_sources":"RESTRICTED_SOURCE"}.items()},
        "user_captures_processed":0,"parser_success_rate":None,"parser_partial_rate":None,"parser_failure_rate":None,
        "loads_with_market_reference":0,"loads_with_antt_reference":0,
        **geographic.get("metrics",{}),
        "municipios_catalogados":len(cities.ids),"hubs":hubs,"escopo_ufs":list(STATES.values())})
    write(state_path,state)
    shutil.copy2(ROOT/"index.html",args.output/"index.html")
    shutil.copytree(ROOT/"assets",args.output/"assets",dirs_exist_ok=True)
    if getattr(args,"browser_runtime",False):
        from .runtime import install
        install(args.output/"runtime",args.cache,ROOT)
    return read(data/"meta.json")

def osrm(a,b):
    delay=1.1-(monotonic()-getattr(osrm,"previous",0))
    if delay>0: sleep(delay)
    osrm.previous=monotonic()
    coords=";".join(f'{x["lon"]},{x["lat"]}' for x in (a,b))
    result=download("https://routing.openstreetmap.de/routed-car/route/v1/driving/"+coords+"?overview=false&steps=false&alternatives=false")
    return float(result["routes"][0]["distance"])/1000

def main():
    p=argparse.ArgumentParser(description="Gera o snapshot independente de busca de fretes")
    p.add_argument("--demo",action="store_true")
    p.add_argument("--public",action="store_true")
    p.add_argument("--refresh-ibge",action="store_true")
    p.add_argument("--browser-runtime",action="store_true",help="Inclui o runtime verificado da análise privada")
    p.add_argument("--osrm",action="store_true",help="Apoio manual e limitado do protótipo; não usar em publicação agendada")
    p.add_argument("--now")
    p.add_argument("--output",type=Path,default=ROOT/"dist")
    p.add_argument("--cache",type=Path,default=ROOT/".cache")
    p.add_argument("--inputs",type=Path,default=ROOT/"data/manual_authorized")
    args=p.parse_args()
    if args.osrm and (args.public or not args.demo): p.error("OSRM demonstrativo só no teste sintético local")
    m=run(args)
    print(json.dumps({k:v for k,v in m.items() if k!="hubs"},ensure_ascii=False))

if __name__=="__main__":
    main()
