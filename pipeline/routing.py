from datetime import timedelta
from .domain import geography, instant, iso

class Router:
    def __init__(self, now, cache, fetch=None, limit=0):
        self.now,self.cache,self.fetch,self.limit=now,cache,fetch,limit

    def route(self,a,b):
        geo=geography(a,b)
        if a["ibge"]==b["ibge"]: return {"km":0,"metodo":"MESMO_MUNICIPIO"}
        k="carro-v1:"+":".join(str(x) for c in (a,b) for x in (c["lat"],c["lon"]))
        if geo is None: return {"km":None,"metodo":"SEM_COORDENADAS"}
        old=self.cache.get(k)
        if old and instant(old["at"])+timedelta(days=30)>self.now:
            return {"km":old["km"],"metodo":"OSRM_ESTIMADO"}
        if self.fetch and self.limit>0:
            self.limit-=1
            try:
                km=self.fetch(a,b)
                if 0<km<20000 and km>=geo*.9:
                    self.cache[k]={"at":iso(self.now),"km":round(km,1)}
                    return {"km":round(km,1),"metodo":"OSRM_ESTIMADO"}
            except (ValueError,OSError,KeyError,IndexError,TypeError):
                pass
        return {"km":round(geo,1),"metodo":"GEODESICA"}
