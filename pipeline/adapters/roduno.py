import re
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

URL="https://roduno.com.br/fretes/carga-de-primavera-mt"

def public_links(html):
    return sorted({"https://roduno.com.br"+a["href"] for a in BeautifulSoup(html,"html.parser").select("a[href]")
        if re.fullmatch(r"/fretes/(?:estado/[a-z]{2}|carga-de-[a-z0-9-]+)",a["href"])},
        key=lambda url:(not url.endswith(("/mt","-mt")),url))

def parse(html,url=URL):
    rows=[]
    for card in BeautifulSoup(html,"html.parser").select("article"):
        text=" ".join(card.get_text(" ",strip=True).split())
        m=re.search(r"Origem\s+(.+?\s*-\s*[A-Z]{2})\s+Destino\s+(.+?\s*-\s*[A-Z]{2})\b(.*?)\s+(\d{2}/\d{2}/\d{4} às \d{2}:\d{2})",text,re.I)
        if not m:continue
        price=re.search(r"R\$\s*[\d.]+,\d{2}",m[3])
        stamp=datetime.strptime(m[4],"%d/%m/%Y às %H:%M").replace(tzinfo=ZoneInfo("America/Cuiaba"))
        vehicle=re.search(r"rodotrem|graneleiro|bitrem|basculante|toco",m[3],re.I)
        rows.append(dict(origem=m[1],destino=m[2],valor_original=price[0] if price else None,veiculo=vehicle[0] if vehicle else None,
            produto=None,peso=None,fonte="Roduno",url=url,tipo_url="listagem",data_exibida=m[4],data_local=stamp.date().isoformat()))
    return rows
