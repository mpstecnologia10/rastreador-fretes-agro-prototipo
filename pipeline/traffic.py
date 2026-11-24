"""Trânsito viário, não fila de descarga. Sem uso de API paga.

Por padrão somente o mapa oficial é consultado pelo usuário. O feed estruturado
é opcional e exige que o titular tenha autorização para publicar os agregados.
Jam ausente não demonstra que a pista está livre.
"""
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parents[1] / "data" / "terminal_traffic.json"
RADIUS_M = 2000
TTL = 900
TERMINALS = [
    ("rumo-tro", "Rumo · Terminal ferroviário", "Rondonópolis/MT", -16.69237, -54.66577,
     "https://www.rumolog.com/sala-de-imprensa/terminal-de-rondonopolis-tem-capacidade-para-receber-ate-2-mil-caminhoes-por-dia-no-auge-da-safra/"),
    ("hbsa-miritituba", "Hidrovias do Brasil · Miritituba", "Itaituba/PA", -4.27239, -55.94501,
     "https://www.semas.pa.gov.br/publicacoes/eia/hbsa_tapajos.pdf"),
    ("graos-barcarena", "Terminal Portuário Graneleiro", "Barcarena/PA", -1.495675, -48.726631,
     "https://www.gov.br/portos-e-aeroportos/pt-br/assuntos/transporte-aquaviario/planejamento-portuario/plano-de-desenvolvimento-e-zoneamento-pdz/arquivos-pdz/PMBelmeViladoConde.pdf"),
]


def near(lat, lon, line):
    """Distância ao trecho, não só aos vértices (projeção tangente local)."""
    previous = None
    for p in line:
        try:
            x, y = float(p["x"]), float(p["y"])
            if not (-180 <= x <= 180 and -90 <= y <= 90):
                raise ValueError()
        except (TypeError, KeyError, ValueError):
            previous = None
            continue
        x, y = (x - lon) * 111320 * math.cos(math.radians(lat)), (y - lat) * 111320
        if math.hypot(x,y) <= RADIUS_M:
            return True
        if previous:
            a, b = previous
            dx, dy = x-a, y-b
            t = max(0., min(1., -(a*dx+b*dy)/(dx*dx+dy*dy))) if (dx or dy) else 0
            if math.hypot(a+t*dx, b+t*dy) <= RADIUS_M:
                return True
        previous = x,y
    return False


def snapshot(feed=None, now=None):
    now = now or datetime.now(timezone.utc)
    jams = (feed or {}).get("jams", [])
    if not isinstance(jams, list):
        jams = []
    terminals = []
    for key, name, city, lat, lon, site in TERMINALS:
        samples = []
        for j in jams:
            if not isinstance(j, dict) or type(j.get("level")) is not int or not 0 <= j["level"] <= 5:
                continue
            stamp = j.get("pubMillis")
            if type(stamp) not in (int, float) or not 0 <= now.timestamp()-stamp/1000 <= TTL:
                continue
            if isinstance(j.get("line"), list) and near(lat, lon, j["line"]):
                samples.append((j["level"], stamp))
        level, stamp = max(samples, default=(None, None))
        terminals.append(dict(id=key,nome=name,cidade=city,lat=lat,lon=lon,fonte_local=site,
                              jam_level=level,observado_em=datetime.fromtimestamp(stamp/1000,timezone.utc).isoformat() if stamp else None))
    return {"schema_version":1, "raio_m":RADIUS_M, "validade_s":TTL, "terminais":terminals}


def main():
    feed = None
    url = os.getenv("WAZE_AUTHORIZED_FEED_URL", "")
    if url and os.getenv("WAZE_AGGREGATE_PUBLICATION_ALLOWED") == "1":
        if not re.fullmatch(r"https://www\.waze\.com/row-partnerhub-api/partners/[0-9]+/waze-feeds/[a-zA-Z0-9-]+(?:\?[^#\s]*)?", url):
            raise ValueError("Endereço do Partner Hub não reconhecido")
        try:
            resp = requests.get(url, timeout=12, allow_redirects=False)
            if resp.status_code == 200:
                body = resp.json()
                if isinstance(body, dict):
                    feed = body
        except (requests.RequestException, ValueError):
            print("Trânsito estruturado indisponível; mapa público preservado.")
    OUT.write_text(json.dumps(snapshot(feed), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
