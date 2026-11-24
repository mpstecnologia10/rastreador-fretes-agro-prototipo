from collections import defaultdict
from .domain import key

class MunicipalityIndex:
    def __init__(self,rows):
        self.names=defaultdict(set)
        for r in rows:
            region=r.get("regiao-imediata") or {}
            uf=region.get("regiao-intermediaria",{}).get("UF",{}).get("sigla")
            if not uf:continue
            name=r["nome"]; entry=(name+"/"+uf,str(r["id"]))
            aliases={name}
            if str(r["id"])=="5107040":aliases.add("Primavera Leste")
            for alias in aliases:
                for s in [alias,alias+" "+uf]:self.names[key(s)].add(entry)
    def resolve(self,value):
        matches=self.names.get(key(value),())
        return next(iter(matches)) if len(matches)==1 else (value,None)
