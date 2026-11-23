"""Triagem comercial: presença no cadastro não é prova de oferta nem de canal."""
from collections import Counter
from .build import ROOT,read,write
from .domain import key

def graph(domains):
    # Contatos gerais, lojas de apps e agendamentos são pistas, não ofertas.
    edges={(r["domain"],p) for r in domains for p in r.get("external_channel_signals",[])}
    return {"scope":"links institucionais; não demonstram contratação",
            "domains_with_link_analysis":sum("external_channel_signals" in r for r in domains),
            "links_to":[{"domain":d,"platform":p} for d,p in sorted(edges)],
            "domains_by_platform":dict(Counter(p for d,p in edges))}

HUBS={key(x) for x in ("Primavera do Leste","Campo Verde","Rondonópolis","Sorriso","Sinop","Lucas do Rio Verde","Nova Mutum","Canarana","Cuiabá")}
def prioritize(rows):
    def score(r):
        return (r["uf"]=="MT" and key(r["municipio"]) in HUBS,r["uf"]=="MT",
            any(w in key(r["empresa"]).split() for w in ("agro","graos","cereais","sementes","fertilizantes")),r["categoria"]=="CTC")
    return sorted((r for r in rows if r["situacao"]=="ATIVO"),key=lambda r:(tuple(-int(v) for v in score(r)),r["cnpj"]))[:1000]

def run():
    companies=read(ROOT/".cache/company-discovery.json")["companies"]
    selected=prioritize(companies)
    write(ROOT/".cache/distribution-priority.json",selected)
    print("RNTRC:",len(companies),"priorizadas:",len(selected),"MT:",sum(r["uf"]=="MT" for r in selected))
    print("Vínculos por plataforma:",dict(Counter(c["platform"] for r in read(ROOT/"data/company_distribution_map.json")["companies"] for c in r["freight_distribution_channels"])))

if __name__=="__main__":
    import sys
    if "--graph" in sys.argv:
        write(ROOT/".cache/source-graph.json",graph(read(ROOT/".cache/scale-scan.json")["domains"]))
    else:run()
