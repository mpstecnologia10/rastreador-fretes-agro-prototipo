"""Read public institutional navigation metadata; never call a discovered API."""
import argparse
import csv
import io
import re
import http.client
import ipaddress
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as XML

from .build import ROOT, read, write
from .domain import iso, safe_url

AGENT="FretesAgroDiscovery"
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args): return None

def get(url,limit=512_000):
    u=urlsplit(url)
    if not safe_url(url) or u.scheme!="https": raise ValueError("origem")
    # Bind the connection to a verified public address; do not follow redirects.
    info=socket.getaddrinfo(u.hostname,443,type=socket.SOCK_STREAM)
    if not info or any(not ipaddress.ip_address(i[4][0]).is_global for i in info): raise ValueError("endereço não público")
    ip=next((i[4][0] for i in info if i[0]==socket.AF_INET),info[0][4][0])
    with socket.create_connection((ip,443),timeout=5) as sock:
        with ssl.create_default_context().wrap_socket(sock,server_hostname=u.hostname) as tls:
            conn=http.client.HTTPSConnection(u.hostname,timeout=5);conn.sock=tls
            conn.request("GET",(u.path or "/")+("?"+u.query if u.query else ""),headers={"User-Agent":AGENT,"Accept-Encoding":"identity"})
            with conn.getresponse() as r:
                if r.status!=200:raise HTTPError(url,r.status,r.reason,r.headers,None)
                raw=r.read(limit+1)
                if len(raw)>limit:raise ValueError("limite")
                return raw

class Nav(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ("a","link") and attrs.get("href"):
            self.links.append((attrs["href"],attrs.get("type","")))

def classify(path,mime=""):
    p=path.lower()
    if p.endswith("manifest.json") or "/comments/" in p: return None
    if "/press-releases/" in p or "/noticias/" in p: return "INSTITUTIONAL_PUBLICATION"
    if "sitemap" in p and p.endswith(".xml"): return "SITEMAP_INDEX"
    if re.search(r"(^|/)(api|docs|developer[s]?|swagger|openapi|redoc)([./-]|$)",p): return "API_DOCUMENTATION_CANDIDATE"
    if re.search(r"rss|atom|feed\+json",mime) or re.search(r"\.(rss|atom|csv|xlsx?|xml|json)$|/feed/?$",p): return "FEED_CANDIDATE"
    if p.endswith(".pdf"): return "DOCUMENT_CANDIDATE"
    if re.search("agendamento|motorista|expedicao|carregamento|/fila|/yms|/tms",p): return "OPERATIONAL_SIGNAL"
    if re.search("fretes|ofertas|cargas",p): return "PUBLIC_DISCOVERY"

def inspect_site(site):
    host=urlsplit(site).hostname
    result={"domain":host,"status":"UNAVAILABLE","candidates":[]}
    try:
        robots=RobotFileParser()
        try: robots.parse(get(site+"robots.txt",200_000).decode(errors="replace").splitlines())
        except HTTPError as err:
            if err.code!=404: raise
            robots.parse([])
        if robots.crawl_delay(AGENT) or robots.request_rate(AGENT):
            result["status"]="DEFERRED_RATE_POLICY"; return result
        paths=[]
        if robots.can_fetch(AGENT,site):
            try:
                nav=Nav(); nav.feed(get(site).decode(errors="replace")); paths.extend(nav.links)
            except (OSError,ValueError): pass
        sm=next((s for s in robots.site_maps() or [] if safe_url(s) and urlsplit(s).netloc==host),site+"sitemap.xml")
        sitemap_ok=False
        if robots.can_fetch(AGENT,sm):
            try:
                raw=get(sm)
                if b"<!DOCTYPE" not in raw.upper():
                    tree=XML.fromstring(raw)
                    if tree.tag.split("}")[-1] not in ("urlset","sitemapindex"): raise ValueError("não é sitemap")
                    sitemap_ok=True
                    paths.extend((n.text,"") for n in tree.iter() if n.tag.split("}")[-1]=="loc" and n.text)
                    if tree.tag.split("}")[-1]=="sitemapindex":
                        children=[n.text for n in tree.iter() if n.tag.split("}")[-1]=="loc" and n.text]
                        children.sort(key=lambda u:(not bool(re.search("page|logistic|frete|transporte",u,re.I)),u))
                        for child in children[:1]:
                            if safe_url(child)!=child or urlsplit(child).hostname!=host or not robots.can_fetch(AGENT,child): continue
                            sub=get(child)
                            if b"<!DOCTYPE" not in sub.upper():
                                paths.extend((n.text,"") for n in XML.fromstring(sub).iter() if n.tag.split("}")[-1]=="loc" and n.text)
                    sitemap_ok=True
            except (ValueError,OSError,XML.ParseError): pass
        # Só o domínio de plataforma explicitamente ligado pela empresa. Não abrir
        # destino, guardar telefone, convite, query, identificador de loja ou anúncio.
        providers={"fretebras.com.br":"Fretebras","puxada.com.br":"Puxada","trizy.com.br":"Trizy",
                   "strada.log.br":"Strada","motz.com.br":"Motz","vectorapp.com.br":"Vector",
                   "wa.me":"WhatsApp","whatsapp.com":"WhatsApp","play.google.com":"Google Play","apps.apple.com":"App Store"}
        signals=set()
        for href,_ in paths:
            try: domain=urlsplit(urljoin(site,href)).hostname or ""
            except ValueError: continue
            for suffix,label in providers.items():
                if domain==suffix or domain.endswith("."+suffix):signals.add(label)
        result["external_channel_signals"]=sorted(signals)
        candidates=set()
        for href,mime in paths:
            url=urljoin(site,href); u=urlsplit(url)
            if u.query or u.fragment or not safe_url(url) or u.hostname!=host: continue
            # Do not publish identifiers, tokens, personal routes, or unreviewed external links.
            if not re.fullmatch(r"/[a-zA-Z./_-]{0,110}",u.path): continue
            mode=classify(u.path,mime)
            if mode and robots.can_fetch(AGENT,url): candidates.add((mode,safe_url(url)))
        result.update(sitemap_found=sitemap_ok,status="METADATA_ONLY" if paths or sitemap_ok else "NO_READABLE_METADATA",
                      candidates=[{"mode":m,"url":u} for m,u in sorted(candidates)[:60]])
    except (OSError,ValueError,http.client.HTTPException): pass
    return result

def api_metrics(rows):
    counts={k:sum(r["api_type"]==v for r in rows) for k,v in [
        ("open_apis","OPEN_API"),("free_key_apis","FREE_API_KEY"),("documented_apis","DOCUMENTED_API"),
        ("partner_apis","PARTNER_API"),("customer_apis","CUSTOMER_API")]}
    return dict(counts,apis_discovered=sum(bool(r["api_type"]) for r in rows),
                apis_with_freight_listing=sum(r["freight_listing"] is True for r in rows),
                apis_with_freight_offer=sum(r["freight_offer"] is True for r in rows),
                active_api_adapters=0,api_freights_collected=0)

def companies():
    rows=list(csv.DictReader(io.StringIO((ROOT/"data/candidates.csv").read_text())))
    rows += read(ROOT/"data/company_discovery_seeds.json")
    return sorted({(r["empresa"],urlsplit(r["url"]).hostname) for r in rows if safe_url(r["url"])})

def discover():
    # Only reviewed institutional homepages, not load boards/login sites.
    sites=read(ROOT/"data/discovery_domains.json")
    with ThreadPoolExecutor(max_workers=4) as pool: rows=list(pool.map(inspect_site,sites))
    return {"checked_at":iso(datetime.now(UTC)),"domains":rows,"api_metrics":api_metrics(read(ROOT/"data/api_registry.json")["entries"])}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,default=ROOT/".cache/discovery.json")
    args=p.parse_args(); result=discover();write(args.output,result)
    print("Domínios:",len(result["domains"]),"candidatos:",sum(len(r["candidates"]) for r in result["domains"]))
