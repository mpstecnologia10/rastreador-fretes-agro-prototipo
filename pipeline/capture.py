"""Deterministic private capture. No network, persistence, or publication."""
import re
from datetime import date, timedelta
from decimal import Decimal

from .domain import STATES, cents, cnpj_ok, compatibility, decimal, geography, key, phone

NUM = r"(?:[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{1,2})?|[0-9]+(?:[,.][0-9]{1,2})?)"
PRODUCTS = {"soja":"Soja", "milho":"Milho", "farelo(?: de soja)?":"Farelo",
            "algodao":"Algodão", "fertilizantes?":"Fertilizantes", "adubos?":"Fertilizantes",
            "ddg":"DDG", "ddgs":"DDGS", "caroco(?: de algodao)?":"Caroço", "sorgo":"Sorgo", "trigo":"Trigo"}
FIELDS = ("origem","destino","produto","carroceria","configuracao","peso_t","valor",
          "tipo_precificacao","empresa","cnpj","telefone","carregamento","observacoes")

def field(value=None, status="CONFIRMADO", options=()):
    return {"valor":value,"confianca":status if value is not None or options else "AUSENTE",
            "opcoes":list(options)}

def number(s, limit=10_000_000):
    s=str(s or "").strip()
    if re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{3})+",s):
        s=s.replace(".","")
    try:
        n=decimal(s)
        return n if n and n<=limit else None
    except ValueError:
        return None

def city_field(fragment, cities):
    cleaned=key(fragment)
    ufs="|".join(v.lower() for v in STATES.values())
    tokens=cleaned.split()
    matches={}
    inferred={}
    for i in range(len(tokens)):
        for j in range(i+1,min(i+9,len(tokens)+1)):
            name=" ".join(tokens[i:j])
            given=j<len(tokens) and re.fullmatch(ufs,tokens[j])
            opts=cities.alias.get(name+" "+tokens[j],[]) if given else cities.alias.get(name,[])
            if name=="primavera":
                opts=[c for c in cities.ids.values() if key(c["nome"]).startswith("primavera") and
                      (not given or c["uf"].lower()==tokens[j])]
                inferred.update((c["ibge"],c) for c in opts)
                continue
            if not opts:
                continue
            for c in opts:
                matches.setdefault(c["ibge"],[]).append((i,j+bool(given),bool(given),c))
    spans=[m for group in matches.values() for m in group]
    survivors={m[3]["ibge"]:m[3] for m in spans if not any(
        x[0]<=m[0] and m[1]<=x[1] and (x[0],x[1])!=(m[0],m[1]) for x in spans)}
    survivors.update({k:v for k,v in inferred.items() if not any(key(c["nome"]).startswith("primavera") for c in survivors.values())})
    opts=sorted(survivors.values(),key=lambda c:(c["nome"],c["uf"]))
    if len(opts)==1:
        code=opts[0]["ibge"]
        explicit=any(m[2] for m in matches.get(code,[]))
        return field(code,"CONFIRMADO" if explicit else "PROVÁVEL",opts)
    return field(None,"INCERTO",opts) if opts else field()

def parse(message, cities, today):
    raw=str(message or "")[:8000]
    f={k:field() for k in FIELDS}
    lines=[line.strip() for line in raw.splitlines() if line.strip()]
    norm=key(raw)
    def combine(name, latest):
        previous=f[name]
        if not latest["opcoes"]: return
        if not previous["opcoes"]: f[name]=latest; return
        choices={c["ibge"]:c for c in previous["opcoes"]+latest["opcoes"]}
        if len(choices)>1: f[name]=field(None,"INCERTO",choices.values())
        elif latest["confianca"]=="CONFIRMADO": f[name]=latest

    for line in lines:
        separate=re.split(r"\s+(?=(?:origem|coleta|destino|entrega)\s*[:=])",line,flags=re.I)
        for fragment in separate:
            label=re.match(r"^[^\w]*(origem|coleta|destino|entrega)\s*[:=]\s*(.+)$",fragment,re.I)
            if label:
                name="origem" if key(label[1]) in ("origem","coleta") else "destino"
                combine(name,city_field(label[2],cities))
        sides=re.split(r"\s+(?:x|para)\s+|\s*[→➜>]\s*|\s+/\s+",line,flags=re.I)
        parts=sides if len(sides)>1 else re.split(r"/(?!\s*(?:"+ "|".join(STATES.values())+r")\b)",line,flags=re.I)
        if len(parts)>=2:
            left,right=city_field(parts[0],cities),city_field(" / ".join(parts[1:]),cities)
            if left["opcoes"] and right["opcoes"]:
                combine("origem",left)
                combine("destino",right)
    for name,items in (("produto",PRODUCTS),("carroceria",{r"graneleir[oa]":"Graneleiro","bau":"Baú","sider":"Sider","tanque":"Tanque","frigorific[oa]":"Frigorífico"}),
                       ("configuracao",{r"rodotrem(?: 9 eixos)?":"Rodotrem",r"bitrem 9 eixos":"Bitrem 9 eixos",r"bitrem(?! 9 eixos)":"Bitrem","truck":"Truck","toco":"Toco","vuc":"VUC",r"(?:carreta )?ls":"Carreta LS",r"carreta(?! ls)":"Carreta",r"9 eixos":"9 eixos"})):
        opts=sorted({v for pattern,v in items.items() if re.search(r"\b(?:"+pattern+r")\b",norm)})
        if name=="configuracao" and len(opts)>1 and "9 eixos" in opts: opts.remove("9 eixos")
        if name=="produto":
            if "Caroço" in opts and "caroco de algodao" in norm and len(re.findall(r"\balgodao\b",norm))==1: opts.remove("Algodão")
            if "Farelo" in opts and "farelo de soja" in norm and len(re.findall(r"\bsoja\b",norm))==1: opts.remove("Soja")
        if opts: f[name]=field(opts[0] if len(opts)==1 else None,"CONFIRMADO" if len(opts)==1 else "INCERTO",opts)
    pattern=re.compile(r"(?<![\d.,])("+NUM+r")\s*(?:/\s*(t(?:on(?:eladas?)?\.?)?)\b|\s+(?:por|a)\s+(t(?:on(?:elada)?\.?)?)\b|\s+(fechado|reais)\b)",re.I)
    prices={(n,"por_tonelada" if m[2] or m[3] else "fechado") for m in pattern.finditer(raw) if (n:=number(m[1]))}
    if len(prices)==1:
        amount, unit=next(iter(prices))
        f["valor"]=field(str(amount)); f["tipo_precificacao"]=field(unit)
    elif not prices:
        vague=re.search(r"(?:R\$\s*|(?:frete|pre[çc]o|valor)\s*[:=]?\s*)("+NUM+r")",raw,re.I)
        if not vague:
            vague=re.search(r"(?<![\d.,])("+NUM+r")\s*(?:ton|t)\b",raw,re.I)
            if vague and number(vague[1],200): vague=None
        if vague and (n:=number(vague[1])):
            f["valor"]=field(str(n),"INCERTO")
    else:
        f["valor"]=field(None,"INCERTO",[str(p[0]) for p in sorted(prices)])
    weight=re.compile(r"(?<![\d.,/])("+NUM+r")\s*(kg|t|ton|tonelada[s]?)\b",re.I)
    weights=set()
    for m in weight.finditer(raw):
        if re.search(r"(?:R\$|\bfrete|\bpre[çc]o|\bvalor)\s*[:=]?\s*$",raw[max(0,m.start()-25):m.start()],re.I):
            continue
        n=number(m[1])
        if n and m[2].lower()=="kg": n/=1000
        if n and n<=200: weights.add(n)
    if len(weights)==1: f["peso_t"]=field(str(next(iter(weights))))
    if len(weights)>1: f["peso_t"]=field(None,"INCERTO",[str(x) for x in sorted(weights)])
    for name,pattern in {
        "empresa":r"(?:^|\n)[^\w]*(?:empresa|transportadora|embarcador)\s*[:=]\s*([^\n;]+)",
        "cnpj":r"\bcnpj\s*[:=]?\s*([A-Z0-9]{2}\.?[A-Z0-9]{3}\.?[A-Z0-9]{3}/?[A-Z0-9]{4}-?[0-9]{2})\b",
        "telefone":r"(?<!\d)(\+?55[\s-]+\(?\d{2}\)?[\s-]*\d{4,5}[\s-]?\d{4}|\(\d{2}\)\s*\d{4,5}[\s-]?\d{4}|(?:fone|telefone|whats(?:app)?|contato)\s*:?\s*\d{10,11})(?!\d)",
        "observacoes":r"(?:^|\n)[^\w]*(?:obs\.?|observa[çc][õo]es|notas?)\s*[:=]\s*([^\n]+)",
    }.items():
        m=re.search(pattern,raw,re.I)
        if not m: continue
        val=m[1].strip()[:300]
        if name=="telefone": f[name]=field(phone(val))
        else: f[name]=field(val,"INCERTO" if name=="cnpj" and not cnpj_ok(val) else "CONFIRMADO")
    load=re.search(r"\b(?:carrega(?:mento|r)?|embarque|coleta)\s*(?:[:=]\s*)?(hoje|amanha|depois de amanha)\b",norm)
    if load:
        f["carregamento"]=field((today+timedelta(days={"hoje":0,"amanha":1,"depois de amanha":2}[load[1]])).isoformat(),"PROVÁVEL")
    else:
        m=re.search(r"\b(?:carrega(?:mento|r)?|embarque)\s*[:=]?\s*(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b",raw,re.I)
        if m:
            try: f["carregamento"]=field(date(int(m[3] or today.year),int(m[2]),int(m[1])).isoformat(),"CONFIRMADO" if m[3] else "PROVÁVEL")
            except ValueError: pass
    return f

def analyze(values, cities, today):
    a,b=(cities.ids.get(str(values.get(k))) for k in ("origem","destino"))
    product=key(values.get("produto"))
    weight=number(values.get("peso_t"),200)
    price=number(values.get("valor"))
    unit=values.get("tipo_precificacao")
    comp,reasons=compatibility(values.get("carroceria"),values.get("configuracao"),float(weight) if weight else None,None)
    total=price if unit=="fechado" else price*weight if price and weight and unit=="por_tonelada" else None
    rt=number(values.get("km_rodoviario"),15000) if a and b else None
    geo=geography(a,b) if a and b else None
    if rt and geo is not None and float(rt)<geo: rt=None
    reference=number(values.get("mercado_valor"))
    try: ref_age=(today-date.fromisoformat(values.get("mercado_data") or "")).days
    except ValueError: ref_age=-1
    market=bool(price and reference and a and b and product and values.get("mercado_rota") is True
                and unit in ("por_tonelada","fechado") and unit==values.get("mercado_unidade") and 0<=ref_age<=30)
    floor=number(values.get("antt_valor"))
    antt=bool(total and floor and rt and values.get("antt_operacao") is True)
    return {"origem":a,"destino":b,"compatibilidade":comp,"motivos":reasons,
            "linha_reta_km":round(geo,1) if geo is not None else None,"rodoviario_km":float(rt) if rt else None,
            "total_centavos":cents(total) if total else None,
            "rs_km_centavos":cents(total/rt) if total and rt else None,
            "valor_50t_centavos":cents(price*50) if price and unit=="por_tonelada" and weight==50 and comp!="INCOMPATIVEL" else None,
            "cnpj_digitos_validos":cnpj_ok(values["cnpj"]) if values.get("cnpj") else None,
            "mercado_diferenca_pct":round(float((price/reference-Decimal(1))*100),1) if market else None,
            "piso_diferenca_centavos":cents(total-floor) if antt else None}
