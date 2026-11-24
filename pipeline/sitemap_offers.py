"""Descoberta limitada ao domínio institucional; sitemap.lastmod não é publicação."""
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from time import sleep
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET
from .build import ROOT,read,write,download,IBGE
from .discovery import AGENT,get
from .domain import safe_url
from .normalizer import MunicipalityIndex

def links(raw,host):
    if b"<!DOCTYPE" in raw.upper():raise ValueError("DOCTYPE")
    tree=ET.fromstring(raw)
    index=tree.tag.split("}")[-1]=="sitemapindex"
    return index,sorted({n.text for n in tree.findall("./*/{*}loc") if n.text and
        safe_url(n.text)==n.text and urlsplit(n.text).hostname==host and
        (index or re.search(r"/(?:frete|carga|oferta)s?/",urlsplit(n.text).path,re.I))})

def parse(html,url,idx,today):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,"html.parser")
    card=soup.select_one("article")
    if not card or len(soup.select("article"))!=1:return None
    stamp=card.select_one('time[itemprop="datePublished"][datetime], time.published[datetime]')
    if not stamp:return None
    day=date.fromisoformat(stamp["datetime"][:10])
    if not today-timedelta(days=15)<=day<=today:return None
    fields={}
    for k in ("origem","destino"):
        m=re.search(k+r"\s*:\s*([\wÀ-ÿ '-]+?\s*[/\-]\s*[A-Z]{2})\b",card.get_text(" ",strip=True),re.I)
        if not m:return None
        fields[k],fields[k+"_ibge"]=idx.resolve(m[1])
        if not fields[k+"_ibge"]:return None
    return dict(fields,url=url,data_local=day.isoformat())

def scan(company,idx):
    host=urlsplit(company["site"]).hostname
    result=dict(host=host,candidatas=[],verificadas=[])
    if host=="play.google.com":return dict(result,status="LOJA_DE_APPS")
    root="https://"+host
    try:
        rules=RobotFileParser()
        try:rules.parse(get(root+"/robots.txt").decode(errors="replace").splitlines())
        except HTTPError as e:
            if e.code!=404:raise
            rules.parse([])
        if rules.request_rate(AGENT) or rules.crawl_delay(AGENT):return dict(result,status="ADIADO")
        queue=[root+"/sitemap.xml"];seen=set()
        for url in queue:
            if len(seen)>=20:break
            if url in seen or not rules.can_fetch(AGENT,url):continue
            seen.add(url);sleep(2)
            try:raw=get(url,3_000_000)
            except HTTPError as e:
                dst=e.headers.get("Location","") if e.headers else ""
                if e.code in (301,302,307,308) and dst and safe_url(dst)==dst and urlsplit(dst).hostname==host:
                    if dst not in queue:queue.append(dst)
                    continue
                raise
            index,urls=links(raw,host)
            if index:queue.extend(u for u in urls if u not in queue)
            else:result["candidatas"].extend(u for u in urls if rules.can_fetch(AGENT,u) and u not in result["candidatas"])
        if company.get("ingestion_possible"):
            for url in result["candidatas"][:30]:
                sleep(2)
                row=parse(get(url),url,idx,date.today())
                if row:result["verificadas"].append(row)
        return dict(result,status="INSPECIONADO" if seen else "NAO_PERMITIDO")
    except (ValueError,OSError,ET.ParseError) as e:return dict(result,status=str(getattr(e,"code",type(e).__name__)))

if __name__=="__main__":
    catalog=read(ROOT/".cache/ibge.json",{"municipios":[]})["municipios"]
    idx=MunicipalityIndex(catalog or download(IBGE))
    with ThreadPoolExecutor(4) as pool:
        results=list(pool.map(lambda c:scan(c,idx),read(ROOT/"data/company_distribution_map.json")["companies"]))
    write(ROOT/".cache/sitemap-offers.json",results)
    print([(r["host"],r["status"],len(r["candidatas"]),len(r["verificadas"])) for r in results])
