"""Editais de serviço de transporte, nunca fretes spot. API oficial de propostas abertas."""
import json
import re
import time
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen
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
    if not re.search(r"(?:servicos? de |empresa para (?:efetuar |realizar )?)transporte (?:rodoviario )?de (?:pedras|cascalho|calcario|graos|milho|soja|fertilizantes|cargas)\b",title):return
    if r["situacaoCompraId"]!=1 or not local_time(r["dataAberturaProposta"])<=now<local_time(r["dataEncerramentoProposta"]):return
    ident=r["numeroControlePNCP"]
    m=re.fullmatch(r"(\d{14})-1-(\d+)/(\d{4})",ident)
    if not m:return
    unit=r["unidadeOrgao"]
    return dict(id=ident,tipo="CONTRATACAO_FUTURA",municipio_comprador=unit["municipioNome"],uf=unit["ufSigla"],
        objeto=r["objetoCompra"].strip(),origem=None,destino=None,preco_frete=None,
        published_at=iso(local_time(r["dataPublicacaoPncp"])),first_seen_at=first.get(ident,iso(now)),
        last_seen_at=iso(now),collected_at=iso(now),expires_at=iso(local_time(r["dataEncerramentoProposta"])),
        fonte=f"https://pncp.gov.br/app/editais/{m[1]}/{m[3]}/{int(m[2])}")

def collect(now):
    path=ROOT/".cache/pncp-opportunities.json"
    first={r["id"]:r["first_seen_at"] for r in read(path,{"editais":[]})["editais"]}
    rows={};errors=[]; scanned=0
    for city in POLOS:
        try:
            for page in range(1,21):
                query=urlencode(dict(dataFinal=(now+timedelta(days=60)).strftime("%Y%m%d"),codigoModalidadeContratacao=6,
                    codigoMunicipioIbge=city,pagina=page,tamanhoPagina=50))
                with urlopen(BASE+"?"+query,timeout=20) as res:
                    if res.status==204:break
                    payload=json.load(res)
                for r in payload["data"]:
                    scanned+=1
                    record=opportunity(r,now,first)
                    if record:rows[record["id"]]=record
                if not payload["paginasRestantes"]:break
                time.sleep(5)
        except HTTPError as e:
            errors.append([city,e.code])
            if e.code in (403,429):break
        except (OSError,ValueError,KeyError) as e:errors.append([city,type(e).__name__])
        time.sleep(5)
    snapshot={"collected_at":iso(now),"checked_records":scanned,"errors":errors,"editais":list(rows.values())}
    write(path,snapshot)
    print("PNCP:",scanned,"analisados;",len(rows),"editais;",errors)

if __name__=="__main__":collect(datetime.now(UTC))
