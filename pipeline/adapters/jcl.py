import re
from bs4 import BeautifulSoup

URL="https://jcltransportes.com.br/fretes-disponiveis/"

def parse(html):
    soup=BeautifulSoup(html,"html.parser")
    rows=[]
    for card in soup.select("article, tr, .carga-card"):
        text=card.get_text(" ",strip=True)
        route=re.search(r"Origem:\s*(.+?)\s+Destino:\s*(.+?\b[A-Z]{2})\b",text)
        link=card.select_one('a[href^="https://jcltransportes.com.br/"]')
        if route and link:
            fields={k:(m[1] if (m:=re.search(rx,text)) else None) for k,rx in
                {"produto":r"Produto:\s*(.+?)(?= Peso:| Valor:|$)","peso":r"Peso:\s*([\d.,]+\s*(?:kg|t))","valor_original":r"(R\$\s*[\d.,]+)"}.items()}
            rows.append(dict(origem=route[1],destino=route[2],fonte="JCL",url=link["href"],**fields))
    return rows
