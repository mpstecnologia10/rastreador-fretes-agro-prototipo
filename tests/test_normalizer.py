import unittest
from pipeline.normalizer import MunicipalityIndex

class CitiesTest(unittest.TestCase):
    def test_alias_and_uniqueness(self):
        def row(code,name,uf):
            return dict(id=code,nome=name,**{"regiao-imediata":{"regiao-intermediaria":{"UF":{"sigla":uf}}}})
        idx=MunicipalityIndex([row(5107040,"Primavera do Leste","MT"),row(5107602,"Rondonópolis","MT"),
            row(1,"Bom Jesus","RS"),row(2,"Bom Jesus","PI")])
        self.assertEqual(idx.resolve("Primavera Leste - MT"),("Primavera do Leste/MT","5107040"))
        self.assertEqual(idx.resolve("Rondonopolis"),("Rondonópolis/MT","5107602"))
        self.assertEqual(idx.resolve("Bom Jesus"),("Bom Jesus",None))
