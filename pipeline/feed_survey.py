"""Survey explicitly linked feeds. Keep format and counts, never item contents."""
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from urllib.error import HTTPError
from xml.etree import ElementTree as ET
from .build import ROOT,read,write
from .discovery import get,AGENT
from .domain import key

def probe(url):
    result={"url":url,"status":"UNAVAILABLE"}
    try:
        robots=RobotFileParser()
        try: robots.parse(get("https://"+urlsplit(url).hostname+"/robots.txt",200000).decode(errors="replace").splitlines())
        except HTTPError as e:
            if e.code!=404:raise
            robots.parse([])
        if not robots.can_fetch(AGENT,url) or robots.crawl_delay(AGENT) or robots.request_rate(AGENT):return dict(result,status="DEFERRED")
        raw=get(url,1000000)
        if b"<!DOCTYPE" in raw.upper():return dict(result,status="NOT_XML_FEED")
        root=ET.fromstring(raw);fmt=root.tag.rsplit("}",1)[-1]
        if fmt not in ("rss","feed","RDF"):return dict(result,status="NOT_XML_FEED")
        items=[i for i in root.iter() if i.tag.rsplit("}",1)[-1] in ("entry","item")]
        hints=0
        for i in items:
            title=key(next((t.text for t in i if t.tag.rsplit("}",1)[-1]=="title"),""))
            hints+=any(x in title for x in ("frete disponivel","carga disponivel","oferta de carga","fretes disponiveis"))
        return dict(result,status="VALID_FEED",fmt=fmt,entries=len(items),listing_title_signals=hints)
    except (OSError,ValueError,ET.ParseError):return result

if __name__=="__main__":
    urls={}
    for r in read(ROOT/".cache/scale-scan.json")["domains"]:
        for c in r["candidates"]:
            if c["mode"]=="FEED_CANDIDATE" and "/feed" in urlsplit(c["url"]).path:
                host=urlsplit(c["url"]).hostname
                if host not in urls or len(c["url"])<len(urls[host]):urls[host]=c["url"]
    with ThreadPoolExecutor(8) as pool: rows=list(pool.map(probe,urls.values()))
    write(ROOT/".cache/feed-survey.json",{"results":rows})
