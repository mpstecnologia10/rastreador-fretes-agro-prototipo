import json
import tempfile
import unittest
from pathlib import Path
from datetime import UTC,datetime
from pipeline.acquisition import collect
from pipeline.discovery import classify
from pipeline.company_discovery import extract
from pipeline.adapters.authorized import AuthorizedFile

class DiscoveryTest(unittest.TestCase):
    def test_cascade_isolated_failures(self):
        now=datetime(2026,11,23,tzinfo=UTC)
        common=dict(docs_url="https://example.org/docs",permission_ref="https://example.org/license",
                    permission_until="2028-01-01T00:00:00Z",publish=True,allow_automated_read=True,free_access=True,
                    requires_auth=False,company="QA",publisher_url="https://example.org/",adapter="authorized_json")
        def source(name,mode,**extra):
            return dict(common,id="feed-"+name,mode=mode,url="https://example.org/"+name)|extra
        attempted=[]
        def get(url,_limit):
            attempted.append(url)
            if url.endswith("/missing"):raise OSError()
            if url.endswith("robots.txt"):return b"User-agent: *\nDisallow: /restricted"
            return b'{"schema_version":1,"cargas":[{"id_oferta":"test"}]}'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            results=collect([source("missing","OPEN_API"),source("contract","CUSTOMER_API"),source("restricted","PUBLIC_FEED"),
                             source("feed","PUBLIC_FEED"),source("site","OPEN_INGEST")],path,now,get)
            self.assertEqual([r["status"] for r in results],["UNAVAILABLE_OR_INVALID","SKIPPED","SKIPPED","STAGED","STAGED"])
            for policy in json.loads((path/"manifest.json").read_text())["feeds"]:
                self.assertEqual(AuthorizedFile(path,policy,now,True).healthcheck()[0]["id_oferta"],"test")
            self.assertFalse(any(u.endswith(("/contract","/restricted")) for u in attempted))
    def test_classification(self):
        self.assertEqual(classify("/page-sitemap.xml"),"SITEMAP_INDEX")
        self.assertEqual(classify("/docs/api"),"API_DOCUMENTATION_CANDIDATE")
        self.assertEqual(classify("/agendamento"),"OPERATIONAL_SIGNAL")
    def test_company_only(self):
        rows=extract(["categoria;uf;cnpj;razao_social","TAC;MT;11.222.333/0001-81;Pessoal","ETC;MT;11.222.333/0001-81;Empresa QA"])
        self.assertEqual([r["empresa"] for r in rows],["Empresa QA"])
