"""Public regional directory. A local unit is not proof of an available load."""
import json
from pathlib import Path
from urllib.parse import urlsplit


DATA = Path(__file__).resolve().parents[1] / "data"
BOTUVERA = "https://botuvera.com/agenciamento-de-cargas/"
# The operator lists these branches and labels the main number as its matriz.
# Do not use per-person numbers, denunciation lines or assume a phone has WA.
BOTUVERA_UNITS = {
    "MT": ("Canarana", "Campo Novo do Parecis", "Campo Verde", "Cuiabá",
           "Lucas do Rio Verde", "Nobres", "Nova Mutum", "Primavera do Leste",
           "Rondonópolis", "Sapezal", "Sinop", "Sorriso"),
    "GO": ("Catalão", "Rio Verde"), "PR": ("Paranaguá",),
    "MG": ("Uberaba",), "SP": ("Paulínia",), "TO": ("Colinas do Tocantins",),
}


def https_url(value):
    if not isinstance(value, str):
        return None
    u = urlsplit(value)
    return value if u.scheme == "https" and u.hostname and not u.username and not u.password else None


def build_radar(data_dir=DATA):
    data_dir = Path(data_dir)
    records = {}

    def add(name, city, uf, site, evidence, role):
        if not all((name, city, uf, https_url(evidence))):
            return
        records[name.casefold(), city.casefold(), uf] = dict(
            nome=name, cidade=city, uf=uf, site=https_url(site) or evidence,
            evidencia=evidence, vinculo=role, telefone=None, whatsapp=None,
            contato_fonte=None)

    mapped = json.loads((data_dir / "company_distribution_map.json").read_text())["companies"]
    for r in mapped:
        add(r["empresa"], r.get("cidade"), r.get("uf"), r.get("site"), r.get("site"),
            "Presença municipal documentada")

    local = json.loads((data_dir / "geo_entities.json").read_text())["entities"]
    for r in local:
        if r.get("confianca") != "CONFIRMED":
            continue
        add(r.get("empresa_associada"), r.get("cidade"), r.get("uf"), r.get("website"),
            r.get("origem_dado"), r.get("nome"))

    for uf, cities in BOTUVERA_UNITS.items():
        for city in cities:
            add("Botuverá", city, uf, BOTUVERA, BOTUVERA,
                "Unidade de agenciamento · contato da matriz")

    for row in records.values():
        if row["nome"] == "RDM Transportes" and row["cidade"] == "Rondonópolis":
            row.update(telefone="+556634236777", whatsapp="+556634236777",
                       contato_fonte="https://rdmtransportes.com.br/")
        elif row["nome"] == "Botuverá":
            row.update(telefone="+556634114999", whatsapp="+556634114999", contato_fonte=BOTUVERA)
        elif row["nome"] == "Unicotton" and row["cidade"] == "Primavera do Leste":
            site = "https://www.unicotton.com.br/"
            row.update(site=site, telefone="+556635001400", contato_fonte=site)

    return {"companies": sorted(records.values(), key=lambda r: (r["uf"], r["cidade"], r["nome"]))}


if __name__ == "__main__":
    target = DATA / "company_radar.json"
    target.write_text(json.dumps(build_radar(), ensure_ascii=False, indent=2) + "\n")
