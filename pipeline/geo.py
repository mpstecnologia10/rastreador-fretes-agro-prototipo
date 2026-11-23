"""Geographic discovery. Never imports freight offers or private registries."""
import argparse
import json
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .build import ROOT, read, write
from .domain import cnpj_ok, geography, instant, iso, key, safe_url

ENDPOINT="https://overpass-api.de/api/interpreter"
TARGETS=("5107040","5102678","5107602")
RULES=[
 ("DRY_PORT",r"porto seco|dry port"),("RAIL_TERMINAL",r"railway terminal|terminal ferroviario|railway freight"),
 ("ROAD_TERMINAL",r"truck stop|truck terminal|terminal rodoviario de cargas"),
 ("FERTILIZER",r"fertiliz|adubos"),("COOPERATIVE",r"cooperativ"),("SILO",r"\bsilos?\b|grain storage"),
 ("CEREALISTA",r"cerealista"),("TRADING",r"\btrading\b"),("PORT",r"\bporto\b|harbour|port terminal"),
 ("AGRO_INDUSTRY",r"agroindustr|esmagadora|agricultural facility|industrial agriculture"),
 ("WAREHOUSE",r"armaz|warehouse|storage|deposito"),("TRANSPORT_COMPANY",r"transportadora|transportes|trucking"),
 ("LOADING_POINT",r"carregamento|expedicao|loading|balanca rodoviaria"),("YARD",r"patio|depot"),
 ("LOGISTICS_CENTER",r"logistic|terminal|industrial"),
]
FREIGHT=re.compile(r"fretes|ofertas.de.cargas|cargas.disponiveis",re.I)
PORTAL=re.compile(r"agendamento|motorista|transportador|expedi[cç]|carregamento|\bfila\b|\byms\b|\btms\b",re.I)

def query(hub, radius=18000):
    code,name,uf,lat,lon=hub
    near=f"(around:{radius},{lat},{lon})"
    return "[out:json][timeout:25];(" + "".join(
        f'nwr["{tag}"~"{values}",i]{near};' for tag,values in (
          ("building","^(warehouse|silo|storage)$"),("man_made","^(silo|storage_tank)$"),
          ("industrial","warehouse|logistic|grain|port|depot|agriculture|storage"),
          ("railway","freight_terminal"),("amenity","truck_stop"),("office","logistics"),
          ("landuse","port"),("name","silo|armaz|cerealista|cooperativ|terminal|transportes|fertiliz|grãos|graos|pátio|patio|agroindustr")
        )) + ");out center 700;"

def fetch(q):
    req=Request(ENDPOINT+"?"+urlencode({"data":q}),headers={"User-Agent":"RastreadorFretesAgroPrototype/1.0","Accept":"application/json"})
    with urlopen(req,timeout=40) as response:
        if response.geturl()!=req.full_url: raise ValueError("redirecionamento Overpass")
        raw=response.read(4_000_001)
    if len(raw)>4_000_000: raise ValueError("resposta excede limite")
    data=json.loads(raw)
    if data.get("remark") or not isinstance(data.get("elements"),list): raise ValueError("consulta incompleta")
    return data["elements"]

def entity(row, hub, now):
    tags=row.get("tags",{}); point=row.get("center",row)
    if row.get("type") not in ("node","way","relation") or not isinstance(row.get("id"),int): return None
    lat,lon=point.get("lat"),point.get("lon")
    if not isinstance(lat,(float,int)) or not isinstance(lon,(float,int)) or not (-90<=lat<=90 and -180<=lon<=180): return None
    name=tags.get("name") or tags.get("operator") or tags.get("brand")
    hint=key(" ".join([name or "",*(str(tags.get(t,"")) for t in ("building","industrial","office","landuse","man_made","railway","amenity"))]))
    cat=next((c for c,p in RULES if re.search(p,hint)),"UNKNOWN_LOGISTICS")
    if not name and cat=="UNKNOWN_LOGISTICS": return None
    site=safe_url(tags.get("website") or tags.get("contact:website"))
    road=round(geography({"lat":lat,"lon":lon},{"lat":hub[3],"lon":hub[4]}),1)
    raw=tags.get("ref:cnpj")
    return {"id":f"osm:{row['type']}:{row['id']}","nome":name,"categoria":cat,"cidade":hub[1],"uf":hub[2],
            "ibge":hub[0],"municipio_metodo":"HUB_PROXIMO_NAO_LIMITE_MUNICIPAL","latitude":lat,"longitude":lon,
            "distancia_hub_km":road,"origem_dado":f"https://www.openstreetmap.org/{row['type']}/{row['id']}",
            "website":site,"website_status":"INDICADO_NO_OSM" if site else None,"operador":tags.get("operator"),
            "empresa_associada":tags.get("operator") or tags.get("brand"),"confianca":"PROBABLE" if name and cat!="UNKNOWN_LOGISTICS" else "POSSIBLE",
            "cnpj_indicado":raw if cnpj_ok(raw) else None,"discovered_at":now,"last_checked_at":now,
            "google_maps_search_url":"https://www.google.com/maps/search/?"+urlencode({"api":1,"query":f"{lat},{lon}"}),
            "waze_navigation_url":"https://www.waze.com/ul?"+urlencode({"ll":f"{lat},{lon}","navigate":"yes"}),
            "geo_source_score":max(0,20-round(road))+20*bool(site)+15*(cat!="UNKNOWN_LOGISTICS")+10*bool(re.search(r"graos|soja|milho|algodao|farelo|fertiliz|ddg",hint))}

def match(e, records):
    """Match approved public company-only extracts. Never read CPF or contact fields."""
    def names(s):
        return re.sub(r"\b(?:ltda|eireli|sa|s a|me|epp)\b","",key(s)).strip()
    label=names(e.get("empresa_associada") or e.get("nome"))
    hits=[]
    for r in records:
        if r.get("ibge")!=e["ibge"] or not cnpj_ok(r.get("cnpj")) or not safe_url(r.get("evidencia")): continue
        score=max((SequenceMatcher(None,label,names(r.get(k))).ratio() for k in ("razao_social","fantasia")),default=0) if label else 0
        digits=lambda x:re.sub(r"[^A-Z0-9]","",str(x or "").upper())
        exact=digits(r["cnpj"])==digits(e.get("cnpj_indicado"))
        if exact or score>=.76: hits.append((1.1 if exact else score,r))
    hits.sort(key=lambda h:-h[0])
    if not hits or len(hits)>1 and hits[0][0]-hits[1][0]<.04: return None
    score,r=hits[0]
    return {"cnpj":r["cnpj"],"rntrc":r.get("rntrc"),"evidencia":safe_url(r.get("evidencia")),
            "confianca":"CONFIRMED" if score>1 else "PROBABLE" if score>=.9 else "POSSIBLE"}

def platforms(entities, evidence):
    out=[]
    for e in entities:
        site=e.get("website")
        if not site: continue
        host=urlsplit(site).hostname
        links=[]
        for raw in evidence.get(host,[]):
            if isinstance(raw,dict):
                link=safe_url(raw.get("url")); proof=safe_url(raw.get("evidencia"))
                if link and proof and raw.get("classe") in ("OPERATIONAL_PORTAL","CANDIDATE_FREIGHT"):
                    links.append(dict(raw,url=link,evidencia=proof))
            elif (u:=safe_url(raw)) and (FREIGHT.search(u) or PORTAL.search(u)):
                links.append({"url":u,"classe":"CANDIDATE_FREIGHT" if FREIGHT.search(u) else "OPERATIONAL_PORTAL"})
        out.append({"entidade_id":e["id"],"empresa":e.get("empresa_associada") or e["nome"],
                    "website":site,"dominio":host,"portais":links,"ingestao_permitida":False})
    return out

def sitemap_candidates(content, trusted_host):
    """Inspect a permitted local sitemap export, never crawl the resulting URLs."""
    if len(content)>2_000_000 or b"<!DOCTYPE" in content.upper():
        raise ValueError("sitemap fora do escopo")
    tree=ElementTree.fromstring(content)
    return sorted({u for node in tree.iter() if node.tag.rsplit("}",1)[-1]=="loc"
                   and (u:=safe_url(node.text)) and urlsplit(u).hostname==trusted_host
                   and (FREIGHT.search(urlsplit(u).path) or PORTAL.search(urlsplit(u).path))})

def summarize(entities, maps):
    cats=Counter(e["categoria"] for e in entities)
    return {"geo_entities_total":len(entities),"silos_discovered":cats["SILO"],"warehouses_discovered":cats["WAREHOUSE"],
            "terminals_discovered":sum(cats[c] for c in ("PORT","DRY_PORT","ROAD_TERMINAL","RAIL_TERMINAL")),
            "cooperatives_discovered":cats["COOPERATIVE"],"transport_companies_geo":cats["TRANSPORT_COMPANY"],
            "geo_entities_with_website":sum(bool(e["website"]) for e in entities),
            "geo_entities_linked_to_cnpj":sum(bool((e.get("registro") or {}).get("cnpj")) for e in entities),
            "geo_entities_linked_to_rntrc":sum(bool((e.get("registro") or {}).get("rntrc")) for e in entities),
            "geo_to_freight_source_conversions":len({p["url"] for r in maps for p in r["portais"] if p["classe"]=="VERIFIED_ALLOWED_FREIGHT"})}

def run(codes, refresh, cache, output, company_records=(), evidence=None):
    now=datetime.now(UTC); now_s=iso(now)
    hubs={h[0]:h for h in read(ROOT/"data/hubs.json")}
    # Barcarena joins the discovery corridors; the existing freight hubs remain untouched.
    hubs["1501303"]=["1501303","Barcarena","PA",-1.51,-48.62]
    previous=read(output/"geo_entities.json",{})
    old={e["id"]:e for e in previous.get("entities",[])}
    seen={}; statuses={}
    for code in codes:
        path=cache/("overpass-"+code+".json"); saved=read(path,{})
        q=query(hubs[code])
        if refresh and (saved.get("query")!=q or instant(saved["checked_at"])<now-timedelta(days=14)):
            try:
                saved={"query":q,"checked_at":now_s,"elements":fetch(q)}
                write(path,saved)
            except (OSError,ValueError,TypeError):
                statuses[code]="CACHE_ANTIGO" if saved else "FONTE_INDISPONIVEL"
        statuses.setdefault(code,"OK" if saved else previous.get("status",{}).get(code,"SEM_CACHE"))
        for row in saved.get("elements",[]):
            e=entity(row,hubs[code],saved["checked_at"])
            if not e: continue
            eid=e["id"]
            if eid in seen and seen[eid]["distancia_hub_km"]<=e["distancia_hub_km"]: continue
            e["discovered_at"]=old.get(eid,{}).get("discovered_at",e["discovered_at"])
            e["registro"]=match(e,company_records)
            seen[eid]=e
    for row in read(ROOT/"data/geo_institutional_seeds.json",[]):
        if row["ibge"] not in codes: continue
        h=hubs[row["ibge"]]
        data={"latitude":None,"longitude":None,"municipio_metodo":"DOCUMENTO_INSTITUCIONAL",
              "cidade":h[1],"uf":h[2],"confianca":"CONFIRMED","geo_source_score":30,**row}
        data["google_maps_search_url"]="https://www.google.com/maps/search/?"+urlencode({"api":1,"query":f"{row['nome']}, {h[1]} {h[2]}"})
        registry=match(data,company_records)
        if registry: data["registro"]=registry
        seen[data["id"]]=data
    entities=sorted(seen.values(),key=lambda e:(-e["geo_source_score"],e["id"]))
    clusters={}
    for e in entities:
        row=clusters.setdefault(e["ibge"],{"categorias":{},"logistics_cluster_score":0})
        cat=e["categoria"]; row["categorias"][cat]=row["categorias"].get(cat,0)+1
        row["logistics_cluster_score"]+=2 if cat in ("SILO","WAREHOUSE","COOPERATIVE","CEREALISTA","FERTILIZER") else 1
    maps=platforms(entities,evidence or {})
    write(output/"geo_entities.json",{"attribution":"© OpenStreetMap contributors, ODbL 1.0","license":"https://www.openstreetmap.org/copyright","status":statuses,
         "entities":entities,"clusters":clusters,"metrics":summarize(entities,maps)})
    write(output/"company_platform_map.json",{"entries":maps})
    return summarize(entities,maps)

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hub",action="append")
    parser.add_argument("--refresh",action="store_true")
    parser.add_argument("--registry")
    parser.add_argument("--sitemap",nargs=2,action="append",default=[],metavar=("HOST","XML"))
    from pathlib import Path
    parser.add_argument("--output",type=Path,default=ROOT/"data")
    args=parser.parse_args()
    evidence=read(ROOT/"data/geo_portal_evidence.json",{})
    for host,path in args.sitemap:
        with Path(path).open("rb") as handle: pages=sitemap_candidates(handle.read(2_000_001),host)
        evidence.setdefault(host,[]).extend(pages)
    print(json.dumps(run(args.hub or TARGETS,args.refresh,ROOT/".cache/geo",args.output,
                         read(Path(args.registry)) if args.registry else (),evidence)))
