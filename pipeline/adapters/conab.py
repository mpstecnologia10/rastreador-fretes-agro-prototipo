"""Publica fatos por lote e remete ao documento original, nunca como carga spot."""
from datetime import UTC,datetime
from ..build import ROOT,write
from ..conab_documents import collect

if __name__=="__main__":
    rows=collect(datetime.now(UTC))
    write(ROOT/".cache/conab-public.json",[{
        k:r[k] for k in ("lote","origem","destino","produto","quantidade_kg","valor_por_t","deadline","situacao","id")
    } for r in rows])
