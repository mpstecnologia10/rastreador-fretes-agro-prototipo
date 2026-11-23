"""Stage only reviewed, public, free, read-only source contracts for the shared pipeline."""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from .build import ROOT, read, write
from .discovery import AGENT, get
from .domain import instant, safe_url

def collect(contracts,directory,now,fetch=get):
    feeds=[]; outcomes=[]
    for source in contracts:
        mode=source.get("mode"); url=source.get("url"); name=source.get("id")
        outcome={"source":name,"mode":mode,"status":"SKIPPED"};outcomes.append(outcome)
        if mode not in ("OPEN_API","FREE_DOCUMENTED_API","PUBLIC_FEED","OPEN_INGEST"): continue
        try:
            if (not safe_url(url) or safe_url(url)!=url or not safe_url(source.get("permission_ref"))
                or not safe_url(source.get("docs_url")) or source.get("allow_automated_read") is not True
                or source.get("publish") is not True or source.get("free_access") is not True
                or source.get("requires_auth") is not False or instant(source["permission_until"])<=now): continue
            import re
            if not re.fullmatch(r"feed-[a-z0-9-]{2,50}",name) or any(f["id"]==name for f in feeds): continue
            fmt={"authorized_csv":"csv","authorized_json":"json"}.get(source.get("adapter"))
            if not fmt: continue
            if urlsplit(url).hostname!=urlsplit(safe_url(source["publisher_url"]) or "").hostname: continue
            origin="https://"+urlsplit(url).netloc
            robots=RobotFileParser();robots.parse(fetch(origin+"/robots.txt",200000).decode().splitlines())
            if not robots.can_fetch(AGENT,url) or robots.crawl_delay(AGENT) or robots.request_rate(AGENT): continue
            raw=fetch(url,5_000_000)
            if fmt=="json":
                payload=json.loads(raw)
                if not isinstance(payload,dict) or payload.get("schema_version")!=1 or not isinstance(payload.get("cargas"),list): raise ValueError()
            else:
                if "id_oferta" not in raw.decode("utf-8-sig").splitlines()[0].split(","): raise ValueError()
            file=name+"."+fmt
            directory.mkdir(parents=True,exist_ok=True)
            (directory/file).write_bytes(raw)
            feeds.append(dict(source,file=file,sha256=hashlib.sha256(raw).hexdigest()))
            outcome["status"]="STAGED"
        except (OSError,ValueError,KeyError,TypeError,IndexError):
            outcome["status"]="UNAVAILABLE_OR_INVALID"
    write(directory/"manifest.json",{"schema_version":1,"feeds":feeds})
    return outcomes

if __name__=="__main__":
    print(json.dumps(collect(read(ROOT/"data/public_contracts.json"),ROOT/".cache/automatic-inputs",datetime.now(UTC))))
