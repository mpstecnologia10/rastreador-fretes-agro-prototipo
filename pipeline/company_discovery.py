"""Read public ANTT company records only; no personal contacts or raw dataset storage."""
import csv
import io
import json
import re
from collections import Counter
from urllib.parse import urlsplit
from urllib.request import urlopen
from .build import ROOT, write
from .domain import key, cnpj_ok

URL="https://dados.antt.gov.br/dataset/b4a055d1-97a2-46f1-9461-cb17fbc6b6b3/resource/6026280b-d547-4702-a0ac-3539ae8ff4a3/download/transportadores_rntrc_10_2026.csv"
STATES={"MT","GO","MS","PR","SP","MG","PA","RS"}

def current_resource():
    with urlopen("https://dados.antt.gov.br/api/3/action/package_show?id=rntrc",timeout=8) as r:
        raw=r.read(2_000_001)
    if len(raw)>2_000_000: raise ValueError("metadata")
    options=[]
    for item in json.loads(raw)["result"]["resources"]:
        url=item.get("url","")
        m=re.fullmatch(r"https://dados\.antt\.gov\.br/dataset/[\da-f-]+/resource/[\da-f-]+/download/transportadores_rntrc_(0[1-9]|1[0-2])_(20\d\d)\.csv",url)
        if m:options.append((m[2],m[1],url))
    return max(options)[2] if options else URL

def extract(lines,evidence=URL):
    rows=csv.DictReader(lines,delimiter=";"); results={};counts=Counter()
    for row in rows:
        r={key(k).replace(" ","_"):str(v or "").strip() for k,v in row.items()}
        category=r.get("categoria") or r.get("categoria_transportador") or r.get("tipo_transportador")
        uf=r.get("uf") or r.get("sg_uf"); cnpj=r.get("cnpj") or r.get("cpf_cnpj") or r.get("cpfcnpjtransportador")
        category=(category or "").upper().split(" ")[0]
        if category not in ("ETC","CTC") or uf not in STATES or not cnpj_ok(cnpj): continue
        if cnpj in results or counts[uf]>=2500: continue
        results[cnpj]={"empresa":r.get("razao_social") or r.get("nome_transportador"),"categoria":category,
                       "uf":uf,"cnpj":cnpj,"rntrc":r.get("numero_rntrc"),"municipio":r.get("municipio"),"situacao":r.get("situacao_rntrc"),"evidencia":evidence}
        counts[uf]+=1
        if len(results)>=20000:break
    return list(results.values())

if __name__=="__main__":
    try: source=current_resource()
    except (OSError,ValueError,TypeError,KeyError): source=URL
    try:
        with urlopen(source,timeout=60) as r:
            if urlsplit(r.geturl()).hostname!="dados.antt.gov.br":raise ValueError()
            initial=r.readline(4096)
            print("Cabeçalho RNTRC:",initial.decode("utf-8-sig",errors="replace")[:300] if b";" in initial and b"rntrc" in initial.lower() else "formato não confirmado")
            import itertools
            try: header=initial.decode("utf-8-sig")
            except UnicodeDecodeError: header=initial.decode("latin-1")
            rows=extract(itertools.chain([header],io.TextIOWrapper(r,encoding="latin-1")),source)
        status="OK" if rows else "NO_MATCH_OR_SCHEMA_UNVERIFIED"
    except (OSError,ValueError,csv.Error): rows=[];status="UNAVAILABLE"
    cache=ROOT/".cache/company-discovery.json"
    if rows or not cache.exists():write(cache,{"source":source,"status":status,"companies":rows})
    print(status,len(rows))
