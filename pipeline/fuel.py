"""Snapshot semanal do preço de revenda de diesel S10 nos polos do piloto."""
import json
import unicodedata
from datetime import date
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

PAGE = "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas"
DATA = Path(__file__).resolve().parents[1] / "data"
STATES = {"MATO GROSSO":"MT", "GOIAS":"GO", "MATO GROSSO DO SUL":"MS", "PARANA":"PR",
          "SAO PAULO":"SP", "MINAS GERAIS":"MG", "PARA":"PA", "RIO GRANDE DO SUL":"RS"}


def clean(value):
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().strip().upper()


def summary_link(html):
    for anchor in BeautifulSoup(html, "html.parser").select("a[href]"):
        url = urljoin(PAGE, anchor["href"])
        parts = urlsplit(url)
        if (parts.scheme == "https" and parts.netloc == "www.gov.br"
                and parts.path.startswith("/anp/") and parts.path.lower().endswith(".xlsx")
                and "PRECOS MEDIOS SEMANAIS" in clean(anchor.get_text(" ", strip=True))):
            return url
    raise ValueError("Planilha semanal da ANP não localizada")


def extract(rows, hubs, url):
    index = {(clean(name), uf): str(code) for code, name, uf, *_ in hubs}
    out, period, header = {}, None, {}
    for row in rows:
        if not header:
            if "MUNICIPIO" in [clean(v) for v in row]:
                header = {clean(v): i for i, v in enumerate(row)}
            continue
        get = lambda key: row[header[key]]
        if clean(get("PRODUTO")) != "OLEO DIESEL S10" or clean(get("UNIDADE DE MEDIDA")) != "R$/L":
            continue
        code = index.get((clean(get("MUNICIPIO")), STATES.get(clean(get("ESTADO")))))
        if not code:
            continue
        start, end = (get(key).strftime("%Y-%m-%d") for key in ("DATA INICIAL", "DATA FINAL"))
        if not start <= end <= date.today().isoformat() or period not in (None, (start, end)) or code in out:
            raise ValueError("Semana inconsistente na pesquisa municipal")
        period = (start, end)
        avg, minimum = (float(get(key)) for key in ("PRECO MEDIO REVENDA", "PRECO MINIMO REVENDA"))
        count = int(get("NUMERO DE POSTOS PESQUISADOS"))
        if not (0 < minimum <= avg and count > 0):
            raise ValueError("Preço ou amostra inválida")
        out[code] = {"media": avg, "minimo": minimum, "postos": count}
    if not out:
        raise ValueError("Pesquisa sem observações municipais S10 para os polos")
    return {"fonte": "ANP · Levantamento de Preços de Combustíveis", "url": url,
            "inicio": period[0], "fim": period[1], "municipios": out}


def refresh():
    from openpyxl import load_workbook

    with requests.Session() as session:
        page = session.get(PAGE, timeout=30)
        page.raise_for_status()
        url = summary_link(page.content)
        response = session.get(url, timeout=45)
        response.raise_for_status()
    book = load_workbook(BytesIO(response.content), read_only=True, data_only=True)
    try:
        sheet = next(s for s in book if clean(s.title) == "MUNICIPIOS")
        result = extract(sheet.values, json.loads((DATA / "hubs.json").read_text()), url)
    finally:
        book.close()
    dest = DATA / "fuel.json"
    if dest.exists() and result["fim"] < json.loads(dest.read_text())["fim"]:
        raise ValueError("A resposta é anterior ao snapshot preservado")
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    tmp.replace(dest)
    print(f"ANP S10: {result['fim']}, {len(result['municipios'])} polos pesquisados")


if __name__ == "__main__":
    refresh()
