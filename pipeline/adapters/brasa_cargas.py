import re
from bs4 import BeautifulSoup

# Canonical target of /cargas.
URL="https://brasa-cargas.com.br/loads"

def parse(html):
    rows={}
    for card in BeautifulSoup(html,"html.parser").select("article"):
        parts=list(card.stripped_strings)
        link=card.select_one('a[href^="/loads/"]')
        if not link or "Mercadoria:" not in parts or "Veículo:" not in parts:continue
        i=parts.index("Mercadoria:"); j=parts.index("Veículo:")
        if i<2 or j+1>=len(parts) or not all(re.search(r" [A-Z]{2}$",p) for p in parts[i-2:i]):continue
        path=link["href"]
        if not re.fullmatch(r"/loads/[\w-]+/[\w-]+",path):continue
        rows[path]=dict(origem=parts[i-2],destino=parts[i-1],produto=parts[i+1],veiculo=parts[j+1],
            valor_original=next((p for p in parts if p.startswith("R$")),None),fonte="Brasa Cargas",
            url="https://brasa-cargas.com.br"+path,data_exibida=next((p.split("·")[0].strip() for p in parts if p.startswith("Carregamento:")),None))
    return list(rows.values())
