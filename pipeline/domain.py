import hashlib
import math
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlsplit, urlunsplit

SCHEMA = 1
STATES = dict(zip(("51","52","50","41","35","31","15","43"),("MT","GO","MS","PR","SP","MG","PA","RS")))
PILOT = ("5107040","5102678","5107602")

def key(s):
    return " ".join(re.sub(r"[^a-z0-9]+"," ",unicodedata.normalize("NFKD",str(s or "")).encode("ascii","ignore").decode().lower()).split())

def instant(s):
    t=datetime.fromisoformat(str(s).replace("Z","+00:00"))
    if t.tzinfo is None: raise ValueError("data exige fuso")
    return t.astimezone(UTC)

def iso(t):
    return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00","Z")

def safe_url(value):
    try:
        s=urlsplit(str(value or ""))
        if s.scheme!="https" or not s.hostname or s.username or s.password or s.port not in (None,443):
            return None
        if not re.fullmatch(r"[a-zA-Z0-9.-]+",s.hostname) or "." not in s.hostname or re.search(r"[\\\s\x00-\x1f]",s.path):
            return None
        return urlunsplit(("https",s.hostname,s.path or "/","",""))
    except ValueError:
        return None

def text(s, length=100):
    return " ".join(str(s or "").split())[:length]

def digits(s):
    return re.sub(r"\D","",str(s or ""))

def cnpj_ok(n):
    n=re.sub(r"[. /-]","",str(n or "")).upper()
    if not re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}",n) or len(set(n))==1: return False
    for weights in ([5,4,3,2,9,8,7,6,5,4,3,2],[6,5,4,3,2,9,8,7,6,5,4,3,2]):
        rem=sum((ord(x)-48)*w for x,w in zip(n,weights))%11
        if int(n[len(weights)])!=(0 if rem<2 else 11-rem): return False
    return True

def phone(s):
    n=digits(s)
    if len(n) in (10,11): n="55"+n
    return "+"+n if re.fullmatch(r"55[1-9][0-9](?:9\d{8}|[2-5]\d{7})",n) else None

def decimal(s):
    v=str(s or "").strip()
    if not v: return None
    if "," in v: v=v.replace(".","").replace(",",".")
    try:
        d=Decimal(v)
        if d.is_finite() and 0<d<=Decimal("10000000"): return d
    except InvalidOperation: pass
    raise ValueError("valor numérico inválido")

def cents(d):
    return int((d*100).quantize(Decimal(1),rounding=ROUND_HALF_UP))

def digest(s):
    return hashlib.sha256(s.encode()).hexdigest()[:24]

class Cities:
    def __init__(self,hubs,official=()):
        self.hubs=[h[0] for h in hubs]
        self.ids={}
        for row in official:
            code=str(row["id"])
            if code[:2] in STATES:
                self.ids[code]={"ibge":code,"nome":row["nome"],"uf":STATES[code[:2]],"lat":None,"lon":None}
        for code,name,uf,lat,lon in hubs:
            self.ids[code]={"ibge":code,"nome":name,"uf":uf,"lat":lat,"lon":lon}
        self.alias={}
        for c in self.ids.values():
            for k in {key(c["nome"]),key(c["nome"]+" "+c["uf"])}:
                self.alias.setdefault(k,[]).append(c)
        for alias,code in {"primavera leste":"5107040","primavera leste mt":"5107040","miritituba":"1503606","miritituba pa":"1503606"}.items():
            self.alias.setdefault(alias,[]).append(self.ids[code])

    def resolve(self,value):
        v=str(value or "").strip()
        if v in self.ids: return self.ids[v]
        rows=self.alias.get(key(v),[])
        if len(rows)!=1:
            raise ValueError("município ausente, ambíguo ou fora de cobertura")
        return rows[0]

def compatibility(body,config,weight,publisher):
    b,c=key(body),key(config)
    if any(k in b for k in ("frigor","tanque","sider","bau","cegonha")) or any(k in c for k in ("vuc","toco","truck")) or (weight and weight>55):
        return "INCOMPATIVEL",["Exigência incompatível com o conjunto de referência"]
    if weight and weight>50:
        return "NAO_CONFIRMADA",["Peso anunciado acima da capacidade de referência de 50 t"]
    if "graneleir" in b and ("rodotrem" in c or ("bitrem" in c and "9 eixos" in c)):
        return "PROVAVEL",["Combinação informada; confirme peso e dimensões"]
    return "NAO_CONFIRMADA",["Veículo, configuração ou peso insuficientes para confirmar"]

def temporal(published,valid,now):
    if valid and valid<=now: return "EXPIRADA"
    age=(now-published).total_seconds()/3600
    if age<=12: return "NOVA"
    if age<=36: return "RECENTE"
    if age<=72: return "ANTIGA"
    return "POSSIVELMENTE_EXPIRADA"

def normalize(r,p,now,cities):
    start=cities.resolve(r.get("origem")); end=cities.resolve(r.get("destino"))
    posted=instant(r.get("publicado_em"))
    expiry=instant(r["validade"]) if r.get("validade") else None
    if posted>now+timedelta(minutes=5) or (expiry and expiry<=posted):
        raise ValueError("datas incoerentes")
    external=text(r.get("id_oferta"),80)
    offer=safe_url(r.get("url"))
    if offer and urlsplit(offer).hostname not in {urlsplit(safe_url(p.get("publisher_url")) or "").hostname,
                                                  *(p.get("offer_hosts") or [])}:
        offer=None
    product=text(r.get("produto"))
    if not external or not product or (not offer and not p.get("synthetic")):
        raise ValueError("id, produto e oferta original são obrigatórios")
    body=text(r.get("carroceria")); conf=text(r.get("configuracao"))
    weight=decimal(r.get("peso_t"))
    if weight and weight>200: raise ValueError("peso fora do intervalo")
    value=decimal(r.get("valor")); kind=key(r.get("tipo_valor"))
    if kind not in ("","por tonelada","fechado") or (value is None)!=(kind==""):
        raise ValueError("valor e tipo devem ser informados juntos")
    if value is not None and cents(value)==0: raise ValueError("valor abaixo de um centavo")
    kind={"por tonelada":"por_tonelada","fechado":"fechado","":None}[kind]
    company=text(r.get("transportadora") or p.get("company"))
    raw_cnpj=re.sub(r"[. /-]","",str(r.get("cnpj") or "")).upper()
    fiscal={ "digitos_validos":cnpj_ok(raw_cnpj) if raw_cnpj else None, "situacao":"NAO_CONSULTADA"}
    comp,reasons=compatibility(body,conf,float(weight) if weight else None,company)
    if (comp=="PROVAVEL" and weight is not None and weight<=50
        and p.get("allow_equipment_confirmation") is True
        and r.get("conjunto_25m_50t_confirmado") in (True,"true","sim")):
        comp,reasons="CONFIRMADA",["Conjunto de 25 m/50 t declarado pelo fornecedor; não confirma condições da rota"]
    weight_supported=weight is None or weight==50 or r.get("valor_50t_permitido") in (True,"true","sim")
    normal=value is not None and kind=="por_tonelada" and weight_supported and comp!="INCOMPATIVEL"
    valid_until=iso(expiry) if expiry else None
    credit=text(r.get("referencia_embarcador"),80)
    evidence={"fonte_id":p["id"],"oferta_id":digest(p["id"]+":"+external),"url":offer,"publicado_em":iso(posted),
              "validade":valid_until,"coletado_em":iso(now),"sintetico":bool(p.get("synthetic"))}
    return {"schema_version":SCHEMA,"origem":start,"destino":end,"produto":product,"carroceria":body or None,
            "configuracao":conf or None,"peso_t":float(weight) if weight else None,"preco_original":text(r.get("valor")) if value is not None else None,
            "tipo_precificacao":kind,"valor_centavos":cents(value) if value is not None else None,
            "valor_50t_centavos":cents(value*50) if normal else None,"normalizacao_permitida":normal,
            "empresa":company,"cnpj":fiscal,"rntrc":{"situacao":"CONSULTA_MANUAL","url":"https://consultapublica.antt.gov.br/Site/ConsultaRNTRC.aspx"},
            "contato_empresarial":phone(r.get("contato_empresarial")) if p.get("publish_business_contact") is True else None,
            "publicado_em":iso(posted),"validade":valid_until,"atualidade":temporal(posted,expiry,now),
            "compatibilidade":comp,"motivos_compatibilidade":reasons,"sintetico":bool(p.get("synthetic")),
            "fonte":evidence,"_identity":raw_cnpj if fiscal["digitos_validos"] else key(company),
            "_ref":key(credit),"_record":p["id"]+":"+external}

def geography(a,b):
    if any(v is None for v in (a["lat"],a["lon"],b["lat"],b["lon"])): return None
    p,q=map(math.radians,(a["lat"],b["lat"]))
    dl=math.radians(b["lon"]-a["lon"])
    x=math.sin((q-p)/2)**2+math.cos(p)*math.cos(q)*math.sin(dl/2)**2
    return 6371*2*math.asin(math.sqrt(min(1,x)))
