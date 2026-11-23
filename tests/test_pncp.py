import unittest
from datetime import datetime,UTC
from pipeline.pncp import opportunity
from pipeline.distribution import prioritize

class Procurements(unittest.TestCase):
    now=datetime(2026,11,23,tzinfo=UTC)
    row=dict(objetoCompra="Serviço de transporte de pedras",situacaoCompraId=1,dataAberturaProposta="2026-11-01T12:00",
        dataEncerramentoProposta="2026-12-01T12:00",dataPublicacaoPncp="2026-11-01T11:00",
        numeroControlePNCP="12345678000190-1-000001/2026",unidadeOrgao={"municipioNome":"Tibagi","ufSigla":"PR"})
    def test_separation_and_time(self):
        r=opportunity(self.row,self.now,{self.row["numeroControlePNCP"]:"2026-11-02T00:00:00Z"})
        self.assertEqual(r["first_seen_at"],"2026-11-02T00:00:00Z")
        self.assertEqual(r["expires_at"],"2026-12-01T15:00:00Z")
        self.assertIsNone(r["origem"]); self.assertIsNone(r["preco_frete"])
    def test_not_open(self):
        for patch in (dict(situacaoCompraId=2),dict(dataEncerramentoProposta="2026-11-22T14:00"),dict(objetoCompra="Transporte escolar")):
            self.assertIsNone(opportunity(self.row|patch,self.now,{}))
    def test_rntrc_priority(self):
        row=dict(empresa="Transportadora",uf="MT",cnpj="A",municipio="Primavera do Leste",categoria="ETC",situacao="ATIVO")
        self.assertEqual(prioritize([row|{"situacao":"PENDENTE"},row|{"uf":"GO"},row])[0],row)
