import unittest
from pipeline.company_discovery import extract
from pipeline.conab_documents import parse_layout

class ScaleTest(unittest.TestCase):
    def test_correct_corporate_identifier(self):
        rows=extract(["nome_transportador;cpfcnpjtransportador;categoria_transportador;municipio;uf;situacao_rntrc",
                      "Empresa QA;11.222.333/0001-81;ETC;Campo Verde;MT;ATIVO",
                      "Ignorar;11.222.333/0001-81;TAC;Campo Verde;MT;ATIVO"])
        self.assertEqual([(r["empresa"],r["situacao"]) for r in rows],[("Empresa QA","ATIVO")])

    def test_document_not_spot_offer(self):
        self.assertEqual(parse_layout("Notícia: serviço de transporte de Milho em Grãos"),[])
        layout="""Contratação de serviço de transporte para remoção de Milho em Grãos
Até as 12:00h (horário de Brasília - DF) do
dia 29/10/2026
7 - DOS PREÇOS:
  1    300,50
7.1
ENDEREÇOS – ANEXO II
 1  Campo Grande  MS Conab  79.108.550  Av. Um  Colatina ES Conab  29.700.000 Rua Dois
ANEXO III"""
        rows=parse_layout(layout)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["destino"],"Colatina/ES")
        self.assertEqual(rows[0]["deadline"],"2026-10-29T15:00:00Z")
        self.assertIsNone(rows[0]["configuracao"])
