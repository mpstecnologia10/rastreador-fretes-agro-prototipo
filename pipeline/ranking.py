from datetime import timedelta
from .domain import SCHEMA, digest, geography, instant, iso, key

def merge(rows, state, now):
    out=[]
    by_record={}
    by_common={}
    reserve=state.setdefault("ids",{})
    seen=state.setdefault("seen",{})
    for r in sorted(rows,key=lambda r:(r["publicado_em"],r["_record"])):
        common=(r["_identity"],r["_ref"],r["origem"]["ibge"],r["destino"]["ibge"],key(r["produto"]),key(r["configuracao"]),r["peso_t"])
        hits=by_common.get(common,[]) if r["_identity"] and r["_ref"] else []
        match=by_record.get(r["_record"]) or next((h for h in hits if abs(instant(r["publicado_em"])-instant(h["anchor"]))<=timedelta(hours=48)),None)
        if match is None:
            match={"anchor":r["publicado_em"],"rows":[]}
            out.append(match)
            if r["_identity"] and r["_ref"]: by_common.setdefault(common,[]).append(match)
        match["rows"].append(r)
        by_record[r["_record"]]=match
    result=[]
    emitted=set()
    for g in out:
        rows=g["rows"]
        compat={"NOVA":5,"RECENTE":4,"ANTIGA":3,"POSSIVELMENTE_EXPIRADA":2,"EXPIRADA":1}
        best=max(rows,key=lambda r:(compat[r["atualidade"]],r["publicado_em"],r["valor_centavos"] is not None))
        records=[r["_record"] for r in rows]
        known=[reserve[k] for k in records if k in reserve and reserve[k] not in emitted]
        gid=min(known,key=lambda k:(seen.get(k,{}).get("first",""),k)) if known else digest(records[0])
        if gid in emitted: gid=digest("separated:"+records[0])
        emitted.add(gid)
        history=seen.get(gid,{})
        now_s=iso(now)
        old_prices=history.get("prices",[])
        for r in rows:
            price={"fonte_id":r["fonte"]["fonte_id"],"tipo":r["tipo_precificacao"],"centavos":r["valor_centavos"]}
            last=next((x for x in reversed(old_prices) if x["fonte_id"]==price["fonte_id"]),None)
            if price["centavos"] is not None and (last is None or any(last[k]!=v for k,v in price.items())):
                old_prices.append({**price,"observado_em":now_s})
        evidence=[r["fonte"] for r in {r["_record"]:r for r in rows}.values()]
        independent=len({e["fonte_id"] for e in evidence})
        confidence={"empresa":"CNPJ não consultado","anuncio":"origem identificada" if best["fonte"]["url"] else "fixture",
                    "contato":"empresarial autorizado" if best["contato_empresarial"] else "consultar fonte",
                    "operacao":"confirmar na origem","preco":"informado" if best["valor_centavos"] else "não informado"}
        level="SINTETICA" if best["sintetico"] else "PARCIAL"
        seals=["Municípios resolvidos"]
        if independent>1: seals.append("Observada em mais de uma fonte")
        if best["cnpj"]["digitos_validos"] is True: seals.append("Formato do CNPJ validado")
        alerts=[]
        if best["cnpj"]["digitos_validos"] is False: alerts.append("CNPJ com dígitos inválidos")
        if best["compatibilidade"] in ("NAO_CONFIRMADA","INCOMPATIVEL"): alerts.append("Conjunto não confirmado")
        if best["atualidade"] in ("ANTIGA","POSSIVELMENTE_EXPIRADA","EXPIRADA"): alerts.append("Disponibilidade não confirmada")
        if len({r["contato_empresarial"] for r in rows if r["contato_empresarial"]})>1: alerts.append("Contatos divergentes")
        data={k:v for k,v in best.items() if not k.startswith("_")}
        for rid in records: reserve[rid]=gid
        seen[gid]={"first":history.get("first",now_s),"prices":old_prices[-40:],"last":now_s}
        result.append({**data,"id":gid,"fontes":evidence,"evidencias":evidence,"fontes_distintas":independent,"confianca":level,
                       "historico_precos":old_prices[-20:],
                       "evidencias_confianca":confidence,"selos":seals,"alertas":alerts,"historico_valores":old_prices[-20:],
                       "primeira_vez_vista":seen[gid]["first"],"ultima_vez_vista":now_s})
    return result

def opportunities(hub, loads, router):
    items=[]
    for r in loads:
        o,d=r["origem"],r["destino"]
        geo=0 if hub["ibge"]==o["ibge"] else geography(hub,o)
        if geo is None or geo>150: continue
        empty,loaded=router.route(hub,o),router.route(o,d)
        price=r["valor_centavos"]; n=r["valor_50t_centavos"] if r["tipo_precificacao"]=="por_tonelada" else price
        road=all(t["metodo"] in ("OSRM_ESTIMADO","MESMO_MUNICIPIO") for t in (empty,loaded))
        km_total=round(empty["km"]+loaded["km"],1) if empty["km"] is not None and loaded["km"] is not None else None
        cost=lambda km: round(n/km) if km and n else None
        per_km=cost(km_total) if road else None
        age={"NOVA":25,"RECENTE":19,"ANTIGA":7,"POSSIVELMENTE_EXPIRADA":0,"EXPIRADA":-30}[r["atualidade"]]
        comp={"CONFIRMADA":24,"PROVAVEL":20,"NAO_CONFIRMADA":5,"INCOMPATIVEL":-50}[r["compatibilidade"]]
        parts={"proximidade":round(max(0,35-geo*35/150),1),"atualidade":age,"compatibilidade":comp,
               "corroboracao":min(10,4*(r["fontes_distintas"]-1)),
               "confianca": 0 if r["sintetico"] else (4 if r["fonte"]["url"] else 0),
               "economia":min(8,round(per_km/200,1)) if per_km else 0}
        back={}
        for dist in (50,100,150):
            back[str(dist)]=sum(1 for x in loads if x["id"]!=r["id"] and x["atualidade"] in ("NOVA","RECENTE")
                and x["compatibilidade"]!="INCOMPATIVEL" and (v:=geography(d,x["origem"])) is not None and v<=dist)
        parts["proxima_carga"]=min(6,back["100"])
        items.append({"carga_id":r["id"],"raio_geo_km":round(geo,1),"vazio":empty,"carregado":loaded,
                      "km_total":km_total,"metodo_total":"RODOVIARIO_ESTIMADO" if road else "APROXIMADO",
                      "valor_referencia_centavos":n,"rs_km_operacional_centavos":per_km,
                      "rs_km_carregado_centavos":cost(loaded["km"]) if loaded["metodo"]=="OSRM_ESTIMADO" else None,
                      "rs_ton_centavos":price if r["tipo_precificacao"]=="por_tonelada" else None,
                      "ranking":{"pontos":round(sum(parts.values()),1),"motivos":parts},
                      "retorno":{"ofertas_proximas":back,"potencial":"ALTO" if back["100"]>=5 else "MEDIO" if back["100"]>=2 else "BAIXO"}})
    return sorted(items,key=lambda x:(-x["ranking"]["pontos"],x["raio_geo_km"],x["carga_id"]))
