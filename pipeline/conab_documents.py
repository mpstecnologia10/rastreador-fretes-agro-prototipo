"""Internal freight tender evidence. Results NEVER feed the public spot market."""
import hashlib
import re
import subprocess
from datetime import UTC,datetime
from urllib.robotparser import RobotFileParser
from .build import ROOT,write,read
from .discovery import get,AGENT
from .domain import iso

INDEX="https://www.gov.br/conab/pt-br/atuacao/logistica/remocao-de-estoques/frete-autonomo"

def parse_layout(text):
    if ("ENDEREÇOS – ANEXO II" not in text or not re.search(r"Contratação de serviço de transporte para remoção de",text,re.I)
        or "Milho em Grãos" not in text):
        return []
    prices=dict(re.findall(r"^\s*(\d+)\s+([\d.]+,\d{2})\s*$",text.split("7 - DOS PREÇOS:",1)[-1].split("7.1",1)[0],re.M))
    dates=re.search(r"Até as (\d{1,2}):(\d{2})h \(horário de Brasília - DF\) do\s*\n[^\n]*?dia (\d{2}/\d{2}/\d{4})",text)
    if not dates:return []
    from zoneinfo import ZoneInfo
    h,m,day=dates.groups()
    deadline=datetime.strptime(day+" "+h+":"+m,"%d/%m/%Y %H:%M").replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
    rows=[]
    for line in text.split("ENDEREÇOS – ANEXO II",1)[-1].split("ANEXO III",1)[0].splitlines():
        # Split on column gaps, not on multiword municipality names.
        cep=r"\d{2}\.?\d{3}[.-]?\d{3}"
        route=re.match(r"^\s*(\d+)\s+([\w' -]+?)\s+([A-Z]{2})\s+\S+\s+"+cep+r"\s+.+?\s{2,}([\w' -]+?)\s+([A-Z]{2})\s+\S+\s+"+cep,line)
        if not route:continue
        lot,o,uf,d,duf=route.groups()
        rows.append({"lote":lot,"origem":o.strip()+"/"+uf,"destino":d.strip()+"/"+duf,"produto":"Milho em grãos",
                     "valor_por_t":prices.get(lot),"configuracao":None,"deadline":iso(deadline)})
    return rows

def collect(now):
    from bs4 import BeautifulSoup
    robots=RobotFileParser();robots.parse(get("https://www.gov.br/robots.txt",200000).decode().splitlines())
    def fetch(url,limit):
        if not (url==INDEX or url.startswith(INDEX+"/")) or not robots.can_fetch(AGENT,url) or robots.crawl_delay(AGENT):raise ValueError("fora de escopo")
        return get(url,limit)
    soup=BeautifulSoup(fetch(INDEX,2_000_000),"html.parser")
    links=[a["href"] for a in soup.select("main a[href]") if re.search(r"Aviso de Frete.*\d+/20\d\d",a.get_text(strip=True),re.I)]
    if not links:raise ValueError("sem aviso")
    page=links[0]; soup=BeautifulSoup(fetch(page,2_000_000),"html.parser")
    main=soup.select_one("main"); closed="resultado final" in main.get_text(" ",strip=True).lower()
    pdf=next(a["href"] for a in main.select("a[href]") if "aviso de frete" in a.get_text(strip=True).lower() and a["href"].endswith(".pdf"))
    raw=fetch(pdf,5_000_000)
    if not raw.startswith(b"%PDF-"): raise ValueError("não é PDF")
    layout=subprocess.run(["pdftotext","-layout","-","-"],input=raw,capture_output=True,timeout=20,check=True).stdout.decode()
    rows=parse_layout(layout);seen=iso(now)
    previous=read(ROOT/".cache/conab-lots.json",{"lots":[]})
    first={r["id"]:r["primeira_vez_vista"] for r in previous["lots"]}
    stamp=main.select_one(".documentPublished .value")
    for r in rows:
        rid=pdf+"#lote-"+r["lote"]
        r.update(id=rid,publicada_em=stamp.get_text(strip=True) if stamp else None,
                 primeira_vez_vista=first.get(rid,seen),ultima_vez_vista=seen,coletada_em=seen,
                 classificacao="REAL_FREIGHT_CONFIRMED",modalidade="CONTRATACAO_POR_LOTE",
                 situacao="ENCERRADO" if closed or r["deadline"]<=seen else "REVISAR_EDITAL",publicavel=False)
    write(ROOT/".cache/conab-lots.json",{"source":pdf,"sha256":hashlib.sha256(raw).hexdigest(),"lots":rows})
    return rows

if __name__=="__main__":print("Lotes documentais internos:",len(collect(datetime.now(UTC))))
