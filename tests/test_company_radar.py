import unittest

from pipeline.company_radar import build_radar


class TestRegionalDirectory(unittest.TestCase):
    def test_business_channel_is_separate_from_telephone(self):
        rows = build_radar()["companies"]
        by_name_city = {(r["nome"], r["cidade"]): r for r in rows}
        unica = by_name_city["Unicotton", "Primavera do Leste"]
        self.assertTrue(unica["telefone"])
        self.assertIsNone(unica["whatsapp"])
        self.assertEqual(by_name_city["RDM Transportes", "Rondonópolis"]["whatsapp"], "+556634236777")
        self.assertTrue(by_name_city["Botuverá", "Campo Verde"]["contato_fonte"])
        self.assertEqual(len(by_name_city), len(rows))
        self.assertTrue(all(r["cidade"] and r["uf"] and r["evidencia"] for r in rows))
