import re
from urllib.robotparser import RobotFileParser
from datetime import datetime
import requests
from time import sleep
from bs4 import BeautifulSoup

HOST="https://freteemtemporeal.com.br"
URL=HOST+"/index.php?page1=fretes&estadoOrigem=MT"

def collect():
    with requests.Session() as s:
        agent="FretesAgroDiscovery";s.headers["User-Agent"]=agent
        r=s.get(HOST+"/robots.txt",timeout=12,allow_redirects=False)
        if r.status_code not in (200,404):raise ValueError(f"robots HTTP {r.status_code}")
        rules=RobotFileParser();rules.parse(r.text.splitlines() if r.ok else [])
        if not rules.can_fetch(agent,URL) or rules.crawl_delay(agent) or rules.request_rate(agent):raise ValueError("robots")
        page=s.get(URL,timeout=12,allow_redirects=False);page.raise_for_status()
        if page.status_code!=200:raise ValueError("redirecionamento")
        rows=parse(page.content)
        for row in rows:
            if not rules.can_fetch(agent,row["url"]):continue
            sleep(2)
            detail=s.get(row["url"],timeout=12,allow_redirects=False)
            if detail.status_code in (403,406,429):break
            if detail.status_code==200:apply_detail(row,detail.content)
        return rows

def apply_detail(row,html):
    text=" ".join(BeautifulSoup(html,"html.parser").stripped_strings)
    m=re.search(r"\bData:\s*(\d{2}/\d{2}/\d{4})",text)
    if m:
        row["data_local"]=datetime.strptime(m[1],"%d/%m/%Y").date().isoformat()
        row["data_exibida"]=m[1]
    for field,label,end in [("peso","Peso","Espécie"),("carroceria","Carroceria","Informações")]:
        m=re.search(label+r":\s*(.{1,100}?)\s+"+end,text)
        if m:row[field]=m[1]

def parse(html):
    rows=[]
    for c in BeautifulSoup(html,"html.parser").select("a.freight-card[href]"):
        url=c["href"];route=[n.get_text(strip=True) for n in c.select(".freight-route-text")]
        if not re.fullmatch(re.escape(HOST)+r"/frete/\d+",url) or len(route)!=2 or not route[0].endswith("/ MT"):continue
        def val(sel):
            el=c.select_one(sel);return el.get_text(" ",strip=True) if el else ""
        age=val(".freight-time").lower()
        fields={g.select_one(".freight-label").get_text(strip=True):g.select_one(".freight-value").get_text(strip=True) for g in c.select(".freight-info-group:has(.freight-label):has(.freight-value)")}
        price=val(".freight-price")
        rows.append(dict(origem=route[0],destino=route[1],produto=fields.get("Produto"),peso=fields.get("Peso"),veiculo=fields.get("Veículo"),especie=fields.get("Espécie"),
            valor_original=(price+" "+val(".freight-price-mode")).strip() if "R$" in price else None,data_local=None,data_exibida=None,indicador_listagem=age,fonte="Frete em Tempo Real",url=url))
    return rows
