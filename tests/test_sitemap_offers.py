import unittest
from pipeline.sitemap_offers import links

class SitemapOffers(unittest.TestCase):
    def test_namespace_and_scope(self):
        xml=b'<urlset xmlns="urn:test"><url><loc>https://empresa.com/frete/42</loc></url><url><loc>https://outro.com/carga/1</loc></url><url><loc>https://empresa.com/noticias/soja</loc></url></urlset>'
        self.assertEqual(links(xml,"empresa.com"),(False,["https://empresa.com/frete/42"]))

    def test_no_entity_expansion(self):
        with self.assertRaises(ValueError):links(b'<!DOCTYPE xml><urlset/>',"empresa.com")
