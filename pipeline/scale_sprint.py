"""One snapshot of public corporate directories, not a catalog of freight."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC,datetime
import re
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from .discovery import get,inspect_site,AGENT
from .build import ROOT,read,write
from .domain import iso,safe_url

DIRECTORIES=[
 ("https://www.abtp.org.br/site/composicao.php",".lista.borda p a[href]","TERMINAL_PORTUARIO"),
 ("https://sindisan.com.br/associadas/",".divTableCell a[href]","TRANSPORTE_PORTUARIO"),
 ("https://abrafrutas.org/associados/",".fwpl-item.el-4x1o88 a[href]","EXPORTACAO_FRUTAS"),
 ("https://sindicomis.com.br/nossos-associados/",".elementor-widget-image .elementor-widget-container > a[href]","AGENTE_DE_CARGAS"),
 ("https://fiata.org/directory/br/",'a[rel~="nofollow"][target="_blank"]:has(span.ml-3)',"AGENTE_DE_CARGAS"),
 ("https://www.abisolo.com.br/associados/","div.fusion-text strong a[href]","FERTILIZANTES"),
 ("https://anatc.com.br/empresas-associadas/","h2.elementor-heading-title a[href]","TRANSPORTE_AGRO"),
 ("https://abia.org.br/a-abia/associadas/",".abia-associates .elementor-widget-image a[href]","INDUSTRIA_ALIMENTAR"),
 ("https://abiove.org.br/associados/",".associados_logos a[href]","OLEAGINOSAS"),
 ("https://amabrasil.agr.br/Publicacao.aspx?id=396532","table.table-bordered td a[href]","FERTILIZANTES"),
]

def entries(row):
    url,selector,sector=row; root="https://"+urlsplit(url).hostname
    robots=RobotFileParser()
    try:
        try: robots.parse(get(root+"/robots.txt",200000).decode(errors="replace").splitlines())
        except HTTPError as e:
            if e.code!=404:raise
            robots.parse([])
        if not robots.can_fetch(AGENT,url) or robots.crawl_delay(AGENT) or robots.request_rate(AGENT):return []
        soup=BeautifulSoup(get(url,3000000),"html.parser")
        records=[]
        for a in soup.select(selector):
            href=a.get("href","").strip()
            if href.startswith("http://"): href="https://"+href[7:]
            if not safe_url(href): continue
            u=urlsplit(href);host=u.hostname
            if host==urlsplit(url).hostname or re.search(r"facebook|instagram|youtube|google|linktr|linkedin|whatsapp|wa\.me|twitter|wordpress\.com|bit\.ly",host):continue
            img=a.find("img");label=(img.get("alt") if img else None) or a.get_text(strip=True) or None
            records.append({"domain":host,"sector":sector,"label":label,"evidence":url,"confidence":"LINKED_BY_ASSOCIATION"})
        return records
    except (ValueError,OSError):return []

def run():
    prior=ROOT/".cache/scale-directory.json"
    now=iso(datetime.now(UTC))
    cached=read(prior,{})
    fresh=lambda stamp:bool(stamp) and 0<=(datetime.now(UTC)-datetime.fromisoformat(stamp.replace("Z","+00:00"))).days<14
    rows=list(cached.get("records",[])) if fresh(cached.get("checked_at")) else []
    known={r["evidence"] for r in rows}
    for group in ThreadPoolExecutor(5).map(entries,[d for d in DIRECTORIES if d[0] not in known]): rows.extend(group)
    if rows!=cached.get("records"):write(prior,{"checked_at":now,"records":rows})
    evidence={r["domain"].removeprefix("www."):r for r in rows}
    for url in read(ROOT/"data/discovery_domains.json"):
        host=urlsplit(url).hostname
        evidence.setdefault(host.removeprefix("www."),{"domain":host,"evidence":"data/discovery_domains.json","confidence":"PREVIOUSLY_REVIEWED"})
    snapshot=ROOT/".cache/scale-scan.json"
    prior_scan=read(snapshot,{})
    previous={r["domain"]:r for r in prior_scan.get("domains",[]) if fresh(r.get("checked_at") or prior_scan.get("checked_at"))}
    def inspect(record):
        host=record["domain"];old=previous.get(host)
        if old and (old["status"] not in ("NO_READABLE_METADATA","UNAVAILABLE") or old.get("canonical_checked")):
            return dict(old,checked_at=old.get("checked_at") or prior_scan["checked_at"])
        if old:
            # Only follow an observed canonical-host declaration, never guess an alternate host.
            for path in ("robots.txt",""):
                try:get("https://"+host+"/"+path)
                except HTTPError as err:
                    location=err.headers.get("Location","") if err.headers else ""
                    target=urlsplit(location).hostname
                    if (err.code in (301,308) and safe_url(location) and target!=host and
                        target.removeprefix("www.")==host.removeprefix("www.") and urlsplit(location).path.strip("/")==path):
                        return dict(inspect_site("https://"+target+"/"),domain=host,canonical=target,canonical_checked=True,
                                   evidence=record["evidence"],sector=record.get("sector"),checked_at=now)
                    if err.code in (401,403,429):break
                except (ValueError,OSError):break
                if path=="robots.txt":break
            return dict(old,canonical_checked=True,checked_at=old.get("checked_at") or prior_scan["checked_at"])
        try:return inspect_site("https://"+record["domain"]+"/")|{"evidence":record["evidence"],"sector":record.get("sector")}
        except (ValueError,OSError):return {"domain":record["domain"],"status":"UNAVAILABLE","candidates":[]}
    with ThreadPoolExecutor(12) as pool: results=list(pool.map(inspect,evidence.values()))
    write(ROOT/".cache/scale-scan.json",{"checked_at":now,"domains":results})
    print(len(rows),len(results),sum(r["status"]=="METADATA_ONLY" for r in results))

if __name__=="__main__": run()
