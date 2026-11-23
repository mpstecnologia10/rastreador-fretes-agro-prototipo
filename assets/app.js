const el=id=>document.getElementById(id);
const labels={NOVA:"Nova",RECENTE:"Recente",ANTIGA:"Antiga",POSSIVELMENTE_EXPIRADA:"Possivelmente expirada",EXPIRADA:"Expirada",PROVAVEL:"Provável",CONFIRMADA:"Confirmada pelo anunciante",NAO_CONFIRMADA:"Não confirmada",INCOMPATIVEL:"Incompatível",SINTETICA:"Sintética",PARCIAL:"Parcial",ALTO:"Alto",MEDIO:"Médio",BAIXO:"Baixo"};
const localized=(v)=>labels[v]||v;
const money=new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL"});
const km=new Intl.NumberFormat("pt-BR",{maximumFractionDigits:1});
const date=new Intl.DateTimeFormat("pt-BR",{dateStyle:"short",timeStyle:"short",timeZone:"America/Cuiaba"});
const fold=x=>(x||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
const state={version:null,mode:null,registry:new Map(),loads:new Map(),items:[],count:0,query:null,request:0};
const text=(tag,content,cls)=>{const node=document.createElement(tag);node.textContent=content;if(cls)node.className=cls;return node};
const link=(title,href)=>{const a=text("a",title);try{const u=new URL(href);if(u.protocol!=="https:")return text("span",title);a.href=u.href;}catch{return text("span",title)}a.target="_blank";a.rel="noopener noreferrer";return a};
const city=c=>c.nome+"/"+c.uf;
const value=c=>c==null?"—":money.format(c/100);
const leg=r=>r.km==null?"Sem coordenadas":km.format(r.km)+" km"+(r.metodo==="GEODESICA"?" · linha reta":r.metodo==="OSRM_ESTIMADO"?" · rodoviário estimado":" · mesma cidade");
function options(id,values,all=true){const sel=el(id);sel.replaceChildren(...(all?[new Option("Todos","")]:[]),...values.map(x=>Array.isArray(x)?new Option(x[1],x[0]):new Option(localized(x),x))); }
async function get(path){const r=await fetch(path,{cache:"no-cache"});if(!r.ok)throw new Error("snapshot indisponível");const j=await r.json();if(j.schema_version!==1||typeof j.snapshot_id!=="string")throw new Error("versão de dados incompatível");return j;}
function card(r,o){
  const a=text("article","","card");
  a.append(text("h3",city(r.origem)+" para "+city(r.destino)),text("p",[r.produto,r.carroceria,r.configuracao,r.peso_t!=null?r.peso_t+" t":null].filter(Boolean).join(" · ")));
  for(const label of [localized(r.atualidade),localized(r.compatibilidade),r.sintetico?"Exemplo sintético":"Confiança: "+localized(r.confianca),...r.selos])a.append(text("span",label,"pill"));
  for(const alert of r.alertas)a.append(text("span",alert,"pill alert"));
  const m=text("dl","","metrics");
  for(const [k,v] of [["Km vazio",leg(o.vazio)],["Km carregado",leg(o.carregado)],["Km total",o.km_total==null?"—":km.format(o.km_total)+" km"+(o.metodo_total==="APROXIMADO"?" · aproximado":" · estimado")],["Preço",value(r.valor_centavos)+(r.tipo_precificacao==="por_tonelada"?" / t":"")],["Estimativa para 50 t",value(r.valor_50t_centavos)],["R$/km operacional",value(o.rs_km_operacional_centavos)]]){const d=text("div","");d.append(text("dt",k),text("dd",v));m.append(d);}
  a.append(m,text("p","Rota estimada. Confirme restrições do conjunto antes da viagem.","subtle"));
  a.append(text("p","Potencial de próxima carga: "+localized(o.retorno.potencial)+" · No snapshot, a 50/100/150 km: "+Object.values(o.retorno.ofertas_proximas).join("/")+". Não garante oferta futura."));
  const notes=text("details","");
  notes.append(text("summary","Motivos da posição e sinais de confiança"),
    text("p","Pontuação: "+o.ranking.pontos+" · "+Object.entries(o.ranking.motivos).map(([k,v])=>k+" "+v).join(" · ")),
    text("p",r.motivos_compatibilidade.join("; ")),text("p",Object.entries(r.evidencias_confianca).map(([k,v])=>k+": "+v).join(" · ")),
    text("p","Validação RNTRC disponível manualmente"),link("Consultar ANTT",r.rntrc.url));
  a.append(notes);
  a.append(text("p","Fontes: "+r.fontes.map(f=>state.registry.get(f.fonte_id)?.nome||f.fonte_id).join(", ")+" · Publicada em "+date.format(new Date(r.publicado_em)),"subtle"));
  for(const [i,f] of r.fontes.filter(f=>f.url).entries()) {if(i)a.append(" · ");a.append(link(i?"Outra oferta original":"Abrir oferta original",f.url));}
  if(!r.fontes.some(f=>f.url))a.append(text("p","Exemplo sem oferta original.","subtle"));
  if(r.contato_empresarial && /^\+55\d{10,11}$/.test(r.contato_empresarial)){const a2=text("a","Ligar para contato empresarial");a2.href="tel:"+r.contato_empresarial;a.append(" · ",a2);}
  return a;
}
function render(){
  const radius=Number(el("radius").value),d=fold(el("destination").value);
  const rows=state.items.map(o=>[state.loads.get(o.carga_id),o]).filter(([r,o])=>r&&o.raio_geo_km<=radius&&(!d||fold(city(r.destino)).includes(d))
    &&(!el("product").value||r.produto===el("product").value)&&(!el("config").value||r.configuracao===el("config").value)
    &&(!el("compat").value||r.compatibilidade===el("compat").value)&&(!el("confidence").value||r.confianca===el("confidence").value)
    &&(!el("age").value||r.atualidade===el("age").value)&&(!el("priced").checked||r.valor_centavos!=null)
    &&(!el("source").value||r.fontes.some(f=>f.fonte_id===el("source").value))
    &&(!el("critical").checked||!["EXPIRADA","POSSIVELMENTE_EXPIRADA"].includes(r.atualidade)&&r.compatibilidade!=="INCOMPATIVEL"));
  state.count=rows.length;
  state.query={municipio_ibge:el("city").value,raio_km:radius,resultados:rows.length,
    recentes:rows.filter(([r])=>["NOVA","RECENTE"].includes(r.atualidade)).length,
    compativeis:rows.filter(([r])=>["PROVAVEL","CONFIRMADA"].includes(r.compatibilidade)).length};
  el("count").textContent=rows.length+" resultado(s)";
  el("results").replaceChildren(...(rows.length?rows.map(([r,o])=>card(r,o)):[text("p","Nenhuma oferta corresponde aos filtros neste snapshot. Amplie o raio ou consulte a fonte original.","empty")]));
}
function error(){el("count").textContent="Dados indisponíveis";el("results").replaceChildren(text("p","Não foi possível carregar um snapshot consistente. Recarregue a página.","empty"))}
async function search(){const request=++state.request;state.query=null;const id=el("city").value;if(!/^\d{7}$/.test(id))return;
  try{const r=await get("data/oportunidades/"+id+".json");if(request!==state.request)return;
    if(r.snapshot_id!==state.version||r.modo!==state.mode)throw new Error();
    state.items=r.oportunidades;render();
  }catch{if(request===state.request)error()}}
function showSources(s){
  for(const r of s.fontes){
    state.registry.set(r.id,r);
    const box=text("article","","source-entry");box.append(text("strong",r.nome+" · "+r.classificacao),
      text("div","Automática: "+(r.coleta_automatica?"sim":"não")+" · "+r.status+" · "+r.encontradas+" encontrados / "+r.aproveitadas+" aproveitados"),
      text("div","Tentativa: "+(r.ultima_tentativa||"—")+" · Sucesso: "+(r.ultimo_sucesso||"—"),"subtle"),
      text("p",[r.nota,r.erro].filter(Boolean).join(" ")||"Feed registrado."));
    if(r.url)box.append(link("Site oficial",r.url));
    el("registry").append(box);
    if(r.classificacao==="LINK_ONLY"&&r.url)el("links").append(link(r.nome,r.url));
  }
}
const storage="fretes-agro:diario:1";
function readJournal(){try{const v=JSON.parse(localStorage.getItem(storage)||"[]");return Array.isArray(v)?v:[]}catch{return []}}
el("log").addEventListener("submit",e=>{e.preventDefault();if(!state.query){el("log-status").textContent="Faça uma busca primeiro.";return;}
  const logs=[...readJournal(),{...state.query,modo:state.mode,snapshot_id:state.version,data:new Date().toISOString(),confirmada:el("confirmed").value,
    link_ativo:el("alive").value,segundos:el("elapsed").value===""?null:Number(el("elapsed").value)}].slice(-500);
  try{localStorage.setItem(storage,JSON.stringify(logs));el("log-status").textContent="Observação salva neste navegador.";}catch{el("log-status").textContent="Armazenamento local indisponível."; }});
el("export").addEventListener("click",()=>{const u=URL.createObjectURL(new Blob([JSON.stringify({schema_version:1,buscas:readJournal()},null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=u;a.download="diario-piloto-fretes.json";a.click();setTimeout(()=>URL.revokeObjectURL(u),1500)});
async function start(){
  const [meta,loads,s]=await Promise.all(["meta","cargas","sources_registry"].map(n=>get("data/"+n+".json")));
  if([loads,s].some(v=>v.snapshot_id!==meta.snapshot_id||v.modo!==meta.modo))throw new Error();
  state.version=meta.snapshot_id;state.mode=meta.modo;
  if(meta.modo==="DEMO")el("notice").textContent="Demonstração com ofertas fictícias. Não são fretes disponíveis para contratação.";
  el("updated").textContent="Snapshot: "+date.format(new Date(meta.atualizado_em))+" (Cuiabá) · Raio calculado em linha reta.";
  el("catalog-meta").textContent=s.fontes.length+" fontes mapeadas · "+meta.fontes_ativas+" fontes de cargas ativas · "+meta.reais+" cargas reais neste snapshot.";
  showSources(s);for(const r of loads.cargas)state.loads.set(r.id,r);
  const set=k=>[...new Set(loads.cargas.map(r=>r[k]).filter(Boolean))].sort();
  options("city",meta.hubs.map(c=>[c.ibge,city(c)]),false);options("product",set("produto"));options("config",set("configuracao"));
  options("compat",["PROVAVEL","CONFIRMADA","NAO_CONFIRMADA","INCOMPATIVEL"]);options("confidence",["SINTETICA","PARCIAL"]);
  options("source",[...new Set(loads.cargas.flatMap(r=>r.fontes.map(f=>f.fonte_id)))].map(id=>[id,state.registry.get(id)?.nome||id]));
  options("age",["NOVA","RECENTE","ANTIGA","POSSIVELMENTE_EXPIRADA","EXPIRADA"]);
  el("search").addEventListener("submit",e=>{e.preventDefault();search()});
  for(const id of ["radius","product","config","compat","confidence","source","age","priced","critical","destination"])el(id).addEventListener("input",()=>{if(state.query)render()});
  el("city").addEventListener("change",search);await search();
}
start().catch(error);
