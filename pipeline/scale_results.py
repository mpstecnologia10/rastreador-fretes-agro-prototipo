"""Summarize verified discovery evidence; never turn a candidate into a load."""
import re
from collections import Counter,defaultdict
from .build import ROOT,read,write
from .domain import key,cnpj_ok

OEA="https://www.gov.br/receitafederal/pt-br/assuntos/aduana-e-comercio-exterior/importacao-e-exportacao/oea/operadores-ja-certificados-como-oea/operadores-OEA-ativos"

def oea_companies(path):
    import xlrd
    sheet=xlrd.open_workbook(str(path)).sheet_by_name("ANALITICO")
    out={}
    for i in range(3,sheet.nrows):
        country,cnpj,name,role,_,__,status,___=sheet.row_values(i)
        if country!="BR" or status!="Ativo" or not cnpj_ok(cnpj):continue
        row=out.setdefault(cnpj[:8],{"empresa":name,"raiz_cnpj":cnpj[:8],"roles":set()})
        row["roles"].add(role)
    for row in out.values():
        row["roles"]=sorted(row["roles"]);s=key(row["empresa"])
        row["prioridade"]=3*bool(set(row["roles"])&{"Transportador","Agente de Carga","Depositário","Operador Portuário"})+2*bool(re.search(r"agro|graos|oleo|fertil|cerea|alimento|cooperat|logistic|transport",s))+int("Exportador" in row["roles"])
    return sorted(out.values(),key=lambda r:(-r["prioridade"],r["raiz_cnpj"]))

def run():
    cache=ROOT/".cache"
    if not (cache/"oea.xls").exists():
        from .discovery import get
        blob=get(OEA+"/@@download/file",4_000_000)
        if not blob.startswith(bytes.fromhex("d0cf11e0")):raise ValueError("planilha OEA não reconhecida")
        cache.mkdir(parents=True,exist_ok=True)
        (cache/"oea.xls").write_bytes(blob)
    oea=oea_companies(cache/"oea.xls")
    write(cache/"oea-company-seeds.json",{"source":OEA,"companies":oea,"prioritized":oea[:500]})
    scan=read(cache/"scale-scan.json"); rows=scan["domains"]
    lots=read(cache/"conab-lots.json")["lots"]
    docs=read(ROOT/"data/api_registry.json")["entries"]
    types=Counter(c["mode"] for r in rows for c in r["candidates"])
    feeds=read(cache/"feed-survey.json")["results"]
    statuses=Counter(r["status"] for r in rows)
    sources=read(ROOT/"data/company_platform_map.json")
    sources["sector_directory_domains"]=[{"dominio":r["domain"],"origem":r["evidence"],"segmento":r.get("sector"),
        "estado_inspecao":r["status"],"sitemap":bool(r.get("sitemap_found")),
        "candidatos":[c for c in r["candidates"] if c["mode"] in ("PUBLIC_DISCOVERY","OPERATIONAL_SIGNAL","API_DOCUMENTATION_CANDIDATE","FEED_CANDIDATE")]}
        for r in rows if "evidence" in r]
    sources["reviewed_freight_channels"]=[
        {"empresa":"Fribon","pagina":"https://fribontransportes.com.br/fretes/","canal":"APP_ONLY"},
        {"empresa":"Botuverá","pagina":"https://botuvera.com/agenciamento-de-cargas/","canal":"WHATSAPP_ONLY"},
        {"empresa":"JCL","pagina":"https://jcltransportes.com.br/fretes-disponiveis/","canal":"FRETEBRAS_LINK_ONLY"}]
    write(ROOT/"data/company_platform_map.json",sources)
    metrics={"companies_seeded_oea":len(oea),"companies_prioritized_oea":min(500,len(oea)),
        "domains_discovered":len(rows),"domains_attempted":len(rows),"domains_with_metadata":statuses["METADATA_ONLY"],
        "domains_crawled":statuses["METADATA_ONLY"]+statuses["NO_READABLE_METADATA"],"statuses":dict(statuses),
        "sitemaps_found":sum(bool(r.get("sitemap_found")) for r in rows),"candidate_links":dict(types),
        "open_apis_found":sum(r["api_type"]=="OPEN_API" for r in docs),"freight_sources_confirmed_internal":int(bool(lots)),
        "active_ingestion_sources_public":0,"real_freights_raw_historical":len(lots),
        "real_freights_unique_historical":len({r["id"] for r in lots}),"real_freights_with_price_historical":sum(r["valor_por_t"]!=None for r in lots),
        "historical_by_origin_uf":dict(Counter(r["origem"][-2:] for r in lots)),
        "expired_lots":sum(r["situacao"]=="ENCERRADO" for r in lots),"rodotrem_confirmed":0,"graneleiro_confirmed":0,
        "real_freights_valid_public":0,"source":OEA,"checked_at":scan["checked_at"]}
    metrics.update(companies_seeded=len(oea),companies_prioritized=min(500,len(oea)),domains_verified=metrics["domains_with_metadata"],
        public_feeds_found=sum(r["status"]=="VALID_FEED" for r in feeds),feed_domains_tested=len(feeds),
        feed_title_matches=sum(r.get("listing_title_signals",0) for r in feeds),
        freight_pages_found=sum(c["mode"]=="PUBLIC_DISCOVERY" for r in rows
            if r["domain"].removeprefix("www.") in {"fribontransportes.com.br","botuvera.com","jcltransportes.com.br"}
            for c in r["candidates"]),companies_with_reviewed_freight_channels=len(sources["reviewed_freight_channels"]),
        freight_sources_confirmed=1 if lots else 0,active_ingestion_sources=0,
        real_freights_raw=len(lots),real_freights_valid=sum(r.get("publicavel") is True and r["situacao"]=="ABERTO" for r in lots),
        real_freights_unique=len({r["id"] for r in lots}),real_freights_with_price=sum(bool(r["valor_por_t"]) for r in lots),
        real_freights_by_source={"CONAB_ARQUIVO_INTERNO":len(lots)},
        real_freights_by_state=metrics["historical_by_origin_uf"],real_freights_rodotrem=0,real_freights_graneleiro=0)
    write(ROOT/"data/scale_metrics.json",metrics);print(metrics)

if __name__=="__main__":run()
