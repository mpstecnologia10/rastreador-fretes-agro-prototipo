import unittest
from datetime import date

from pipeline.fuel import extract, summary_link


class FuelTest(unittest.TestCase):
    header = ["DATA INICIAL", "DATA FINAL", "ESTADO", "MUNICÍPIO", "PRODUTO", "UNIDADE DE MEDIDA",
              "PREÇO MÉDIO REVENDA", "PREÇO MÍNIMO REVENDA", "NÚMERO DE POSTOS PESQUISADOS"]
    sample = [date(2025, 1, 5), date(2025, 1, 11), "MATO GROSSO", "RONDONOPOLIS", "OLEO DIESEL S10",
              "R$/l", 7.41, 6.99, 13]
    hubs = [["5107602", "Rondonópolis", "MT"], ["5107040", "Primavera do Leste", "MT"]]

    def test_matching_uf_product_and_missing_observation(self):
        wrong_product = self.sample.copy()
        wrong_product[4] = "OLEO DIESEL"
        wrong_state = self.sample.copy()
        wrong_state[2] = "PARA"
        result = extract([self.header, wrong_product, wrong_state, self.sample], self.hubs, "url")
        self.assertEqual(result["municipios"], {"5107602": {"media": 7.41, "minimo": 6.99, "postos": 13}})
        self.assertEqual(result["fim"], "2025-01-11")

    def test_reject_empty_and_duplicates(self):
        for rows in ([self.header], [self.header, self.sample, self.sample]):
            with self.assertRaises(ValueError):
                extract(rows, self.hubs, "url")

    def test_use_first_official_summary_only(self):
        page = '<a href="https://outro.example/a.xlsx">Preços médios semanais</a><a href="/anp/ok.xlsx">Preços médios semanais</a>'
        self.assertEqual(summary_link(page), "https://www.gov.br/anp/ok.xlsx")
