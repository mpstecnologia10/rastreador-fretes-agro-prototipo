"""Editais de serviço de transporte, nunca fretes spot. API oficial de propostas abertas."""
import json
import re
import time
from datetime import UTC, datetime, timedelta
import requests
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from .build import ROOT, read, write
from .domain import iso, key

BASE="https://pncp.gov.br/api/consulta/v1/contratacoes/proposta"
# Códigos IBGE: nove polos de MT e um corredor de validação no PR.
POLOS=(5107040,4127502,5102678,5107602,5107925,5107909,5105259,5106224,5102702,5103403)

def local_time(s):
    dt=datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))

def opportunity(r, now, first):
    title=key(r["objetoCompra"])
    if not re.search(r"\b(?:transporte (?:rodoviario )?de (?:pedras|cascalho|calcario|graos|milho|soja|fertilizantes|cargas)|(?:contratacao|servicos?) de fretes?|logistica de (?:transporte|escoamento|distribuicao) de (?:graos|milho|soja|cargas))\b",title):return
    if r["situacaoCompraId"]!=1 or not local_time(r["dataAberturaProposta"])<=now<local_time(r["dataEncerramentoProposta"]):return
    ident=r["numeroControlePNCP"]
    m=re.fullmatch(r"(\d{14})-1-(\d+)/(\d{4})",ident)
    if not m:return
    unit=r["unidadeOrgao"]
    return dict(id=ident,tipo="CONTRATACAO_FUTURA",municipio_comprador=unit["municipioNome"],uf=unit["ufSigla"],
        objeto=r["objetoCompra"].strip(),origem=field(r["objetoCompra"],"origem"),destino=field(r["objetoCompra"],"destino"),
        quantidade=field(r["objetoCompra"],"quantidade"),valor_estimado=r.get("valorTotalEstimado"),preco_frete=None,
        published_at=iso(local_time(r["dataPublicacaoPncp"])),first_seen_at=first.get(ident,iso(now)),
        last_seen_at=iso(now),collected_at=iso(now),expires_at=iso(local_time(r["dataEncerramentoProposta"])),
        fonte=f"https://pncp.gov.br/app/editais/{m[1]}/{m[3]}/{int(m[2])}")

def field(text,label):
    m=re.search(r"\b"+label+r"\s*:\s*([^;\n|]{1,90}?)(?=\s+(?:origem|destino|quantidade)\s*:|[;\n|]|$)",text,re.I)
    return m[1].strip() if m else None

def collect(now):
    path=ROOT/".cache/pncp-opportunities.json"
    seed=read(ROOT/"data/pncp_verified.json",{"editais":[]})
    previous={r["id"]:r for r in seed["editais"]+read(path,{"editais":[]})["editais"]}
    first={i:r["first_seen_at"] for i,r in previous.items()}
    rows={};errors=[]; scanned=0; complete=set(); observed=set()
    # Busca nacional adicional pelo CNPJ da matriz da Conab, sem filtro municipal.
    for city in (*POLOS,"CONAB"):
        try:
            for page in range(1,21):
                query=urlencode(dict(dataFinal=(now+timedelta(days=60)).strftime("%Y%m%d"),codigoModalidadeContratacao=6,
                    pagina=page,tamanhoPagina=50,**({"cnpj":"26461699000180"} if city=="CONAB" else {"codigoMunicipioIbge":city})))
                with requests.get(BASE+"?"+query,timeout=20) as res:
                    res.raise_for_status()
                    if res.status_code==204:
                        complete.add(city);break
                    payload=res.json()
                for r in payload["data"]:
                    scanned+=1
                    observed.add(r["numeroControlePNCP"])
                    record=opportunity(r,now,first)
                    if record:rows[record["id"]]=dict(record,ibge_comprador=r["unidadeOrgao"].get("codigoIbge"),consulta=city)
                if not payload["paginasRestantes"]:
                    complete.add(city);break
                time.sleep(5)
        except requests.HTTPError as e:
            code=e.response.status_code
            errors.append([city,code])
            if code in (403,429):break
        except (OSError,ValueError,KeyError) as e:
            errors.append([city,type(e).__name__])
            if not complete and len(errors)>=2:break
        time.sleep(5)
    for i,r in previous.items():
        if (i not in observed and r.get("consulta",r.get("ibge_comprador")) in (set(POLOS)|{"CONAB"})-complete and
            now-timedelta(hours=24)<local_time(r["last_seen_at"])<=now<local_time(r["expires_at"])):
            rows[i]=r
    snapshot={"collected_at":iso(now),"checked_records":scanned,"errors":errors,"editais":list(rows.values())}
    write(path,snapshot)
    print("PNCP:",scanned,"analisados;",len(rows),"editais;",errors)

if __name__=="__main__":collect(datetime.now(UTC))
