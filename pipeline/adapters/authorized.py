import csv
import hashlib
import io
import json
from pathlib import Path

LIMIT = 5_000_000

class AuthorizedFile:
    def __init__(self, directory, policy, now, public=False):
        self.policy = policy
        self.directory = directory.resolve()
        self.now = now
        self.public = public

    def fetch(self):
        from pipeline.domain import instant, safe_url
        p = self.policy
        if (not p.get("permission_ref") or not p.get("company") or
            not safe_url(p.get("publisher_url")) or
            instant(p.get("permission_until")) <= self.now or
            (self.public and p.get("publish") is not True)):
            raise ValueError("autorização ou escopo insuficiente")
        name = Path(p["file"])
        fmt = {"authorized_csv": ".csv", "authorized_json": ".json"}.get(p["adapter"])
        if name.name != str(name) or fmt is None or name.suffix != fmt:
            raise ValueError("arquivo ou adaptador não permitido")
        path = (self.directory / name).resolve()
        if path.parent != self.directory:
            raise ValueError("arquivo fora da entrada autorizada")
        with path.open("rb") as handle:
            raw = handle.read(LIMIT + 1)
        if len(raw)>LIMIT or hashlib.sha256(raw).hexdigest()!=p.get("sha256"):
            raise ValueError("arquivo excede limite ou não corresponde à autorização")
        return raw

    def parse(self, raw):
        if self.policy["adapter"]=="authorized_csv":
            rows=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        else:
            data=json.loads(raw)
            if not isinstance(data, dict) or data.get("schema_version")!=1:
                raise ValueError("schema de entrada não suportado")
            rows=data.get("cargas")
        if not isinstance(rows,list) or len(rows)>10000 or not all(isinstance(r,dict) for r in rows):
            raise ValueError("entrada inválida")
        return rows

    def normalize(self, row, cities):
        from pipeline.domain import normalize
        return normalize(row,self.policy,self.now,cities)

    def healthcheck(self):
        return self.parse(self.fetch())
