"""Check only robots metadata on already curated official URLs. Never fetch ads."""
import csv
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC,datetime
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
from .build import ROOT

def audit(source):
    url=urlsplit(source["url"])
    robots=f"{url.scheme}://{url.netloc}/robots.txt"
    checked=datetime.now(UTC).isoformat(timespec="seconds")
    agent="RastreadorFretesAgroPrototype"
    entry={"robots_url":robots,"checado_em":checked,"robots":"INCONCLUSIVO","feed_publico":None,
           "termos_evidencia":source["termos"] or None}
    try:
        with urlopen(Request(robots,headers={"User-Agent":agent}),timeout=6) as response:
            if urlsplit(response.geturl()).hostname!=url.hostname:
                entry["robots"]="REDIRECIONADO"
            else:
                raw=response.read(100000).decode("utf-8",errors="replace")
                if raw.lstrip().startswith("<"):
                    entry["robots"]="RESPOSTA NÃO É ROBOTS"
                else:
                    parser=RobotFileParser()
                    parser.parse(raw.splitlines())
                    entry["robots"]="CAMINHO PERMITIDO" if parser.can_fetch(agent,source["url"]) else "CAMINHO RESTRITO"
    except HTTPError as e:
        entry["robots"]=f"HTTP {e.code}"
    except OSError:
        entry["robots"]="INDISPONÍVEL"
    if source["id"]=="ibge":
        entry["feed_publico"]="API documentada de municípios; não é fonte de fretes"
    return source["id"],entry

if __name__=="__main__":
    with (ROOT/"data/candidates.csv").open(encoding="utf-8") as source:
        with ThreadPoolExecutor(max_workers=8) as pool:
            print(json.dumps(dict(pool.map(audit,csv.DictReader(source))),ensure_ascii=False,indent=2))
