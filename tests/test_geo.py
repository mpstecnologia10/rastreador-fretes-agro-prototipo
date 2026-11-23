import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from pipeline.geo import entity, match, platforms, run, sitemap_candidates

HUB=("5107040","Primavera do Leste","MT",-15.56,-54.30)
OSM={"type":"way","id":20,"center":{"lat":-15.56,"lon":-54.30},"tags":{"name":"Silo Teste","website":"https://example.org/"}}

class GeoTest(unittest.TestCase):
    def test_poi_is_not_offer_and_match_requires_evidence(self):
        e=entity(OSM,HUB,"2026-11-23T12:00:00Z")
        self.assertEqual(e["categoria"],"SILO")
        self.assertIn("api=1",e["google_maps_search_url"])
        r={"ibge":HUB[0],"razao_social":"Silo Teste LTDA","cnpj":"11.222.333/0001-81","evidencia":"https://example.org/prova"}
        self.assertEqual(match(e,[r])["confianca"],"PROBABLE")
        self.assertIsNone(match(e,[r,r]))
        self.assertFalse(platforms([e],{"example.org":["https://example.org/fretes"]})[0]["ingestao_permitida"])

    def test_cache_and_metrics(self):
        with TemporaryDirectory() as tmp, patch("pipeline.geo.fetch",return_value=[OSM]) as f:
            base=Path(tmp)
            for _ in range(2):
                m=run([HUB[0]],True,base/"cache",base/"snapshot")
                self.assertEqual(m["silos_discovered"],1)
                self.assertEqual(m["geo_to_freight_source_conversions"],0)
            self.assertEqual(f.call_count,1)
            self.assertFalse((base/"snapshot/cargas.json").exists())

    def test_sitemap_scope(self):
        xml=b"<urlset><url><loc>https://example.org/fretes</loc></url><url><loc>https://other.org/agendamento</loc></url></urlset>"
        self.assertEqual(sitemap_candidates(xml,"example.org"),["https://example.org/fretes"])
