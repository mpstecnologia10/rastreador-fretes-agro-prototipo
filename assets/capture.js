const el=id=>document.getElementById(id);
const names={origem:"Origem",destino:"Destino",produto:"Produto",carroceria:"Carroceria",configuracao:"Veículo",peso_t:"Peso (t)",valor:"Valor (R$)",tipo_precificacao:"Unidade do valor",empresa:"Empresa",cnpj:"CNPJ",telefone:"Telefone",carregamento:"Carregamento",observacoes:"Observações"};
const references=["km_rodoviario","mercado_valor","mercado_unidade","mercado_data","mercado_rota","antt_valor","antt_operacao"];
const example="Primavera do Leste MT x Santos SP\nSoja\nRodotrem graneleiro\n50 ton\n470/t\nCarrega amanhã";
const money=n=>n==null?"—":(n/100).toLocaleString("pt-BR",{style:"currency",currency:"BRL"});
let worker,serial=0,municipalities=[], deadline;
function node(tag, label){const n=document.createElement(tag);n.textContent=label;return n;}
function clear(){
  clearTimeout(deadline);worker?.terminate();worker=null;serial++;
  el("capture-form").reset();el("capture-review").reset();el("capture-review").hidden=true;
  el("capture-fields").replaceChildren();el("capture-result").replaceChildren();el("capture-status").textContent="";
}
function review(fields){
  const controls=Object.entries(names).map(([name,label])=>{
    const f=fields[name], wrapper=node("label",label+" ");
    const confidence=node("small",f.confianca);confidence.className="subtle";wrapper.append(confidence);
    let input;
    if(name==="origem"||name==="destino"){
      input=document.createElement("select");
      const suggest=new Set(f.opcoes.map(c=>c.ibge));
      input.append(new Option("Selecione o município",""),...municipalities.filter(c=>suggest.has(c.id)).map(c=>new Option(c.label+" · sugerido",c.id)));
      const group=document.createElement("optgroup");group.label="Demais municípios do catálogo";
      group.append(...municipalities.filter(c=>!suggest.has(c.id)).map(c=>new Option(c.label,c.id)));input.append(group);
      input.value=f.confianca==="CONFIRMADO"?f.valor:"";
    }else if(name==="tipo_precificacao"){
      input=document.createElement("select");input.append(new Option("Não identificado",""),new Option("R$/t","por_tonelada"),new Option("R$ total","fechado"));input.value=f.valor||"";
    }else{
      input=document.createElement("input");input.maxLength=300;input.type=name==="carregamento"?"date":"text";input.value=f.valor??"";
      if(name==="valor"||name==="peso_t")input.inputMode="decimal";
      if(f.opcoes.length>1)wrapper.append(node("small"," · "+f.opcoes.join(" / ")));
    }
    input.id="cap-"+name;
    input.addEventListener("change",()=>{confidence.textContent="EDITADO";el("capture-result").replaceChildren()});
    wrapper.append(input);return wrapper;
  });
  el("capture-fields").replaceChildren(...controls);el("capture-review").hidden=false;
}
function render(r){
  const route=[r.origem,r.destino].map(c=>c?c.nome+"/"+c.uf:"Município não confirmado").join(" → ");
  const dl=node("dl","");dl.className="metrics";
  for(const [k,v] of [["Distância rodoviária",r.rodoviario_km==null?"Não informada":r.rodoviario_km+" km (informada)"],
    ["Linha reta",r.linha_reta_km==null?"Indisponível":r.linha_reta_km+" km · aproximação"],["Valor total estimado",money(r.total_centavos)],
    ["Estimativa para 50 t",money(r.valor_50t_centavos)],["R$/km rodoviário",money(r.rs_km_centavos)],
    ["Compatibilidade",({PROVAVEL:"Provável",INCOMPATIVEL:"Incompatível",NAO_CONFIRMADA:"Não confirmada"})[r.compatibilidade]],
    ["Mercado",r.mercado_diferenca_pct==null?"Sem referência comparável":r.mercado_diferenca_pct.toLocaleString("pt-BR")+"% ante a referência informada"],
    ["Piso ANTT",r.piso_diferenca_centavos==null?"Não avaliado":r.piso_diferenca_centavos===0?"Igual ao valor oficial informado":money(Math.abs(r.piso_diferenca_centavos))+(r.piso_diferenca_centavos<0?" abaixo":" acima")+" do valor oficial informado"],
    ["CNPJ",r.cnpj_digitos_validos==null?"Não informado":r.cnpj_digitos_validos?"Dígitos válidos; situação não consultada":"Dígitos inválidos"],
    ["RNTRC","Não consultado; verifique na ANTT"]]){
    const block=node("div","");block.append(node("dt",k),node("dd",v));dl.append(block);
  }
  const box=node("article","");box.className="card";
  box.append(node("h3",route),dl,node("p",r.motivos.join(" · ")),node("p","Confira disponibilidade, preço, elegibilidade do conjunto e condições com a fonte original. A comparação não é parecer regulatório."));
  el("capture-result").replaceChildren(box);
}
function send(action,value){
  const status=el("capture-status");
  const fail=()=>{clearTimeout(deadline);worker?.terminate();worker=null;status.textContent="Análise local indisponível. Atualize a página ou tente novamente em um navegador atual. O texto não foi enviado."};
  if(!worker){
    try{worker=new Worker(new URL("capture-worker.js",import.meta.url))}catch{fail();return;}
    worker.onmessage=({data})=>{
      if(data.cities){municipalities=data.cities.sort((a,b)=>a.label.localeCompare(b.label,"pt-BR"));return}
      if(data.id!==serial)return;
      clearTimeout(deadline);
      if(data.error){fail();return;}
      status.textContent=data.action==="analyze"?"Análise calculada localmente.":"Interpretação concluída. Revise os campos.";
      if(data.action==="analyze")render(data.result);else review(data.result);
    };
    worker.onerror=fail;
  }
  status.textContent="Processando no navegador…";
  clearTimeout(deadline);deadline=setTimeout(fail,45000);
  const today=new Intl.DateTimeFormat("en-CA",{timeZone:"America/Cuiaba",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date());
  const part=k=>today.find(p=>p.type===k).value;
  worker.postMessage({action,value,today:[part("year"),part("month"),part("day")].join("-"),id:++serial});
}
el("capture-form").addEventListener("submit",e=>{e.preventDefault();el("capture-review").hidden=true;el("capture-review").reset();el("capture-result").replaceChildren();send("parse",el("capture-text").value)});
el("capture-review").addEventListener("submit",e=>{e.preventDefault();const values={};
  for(const key of [...Object.keys(names),...references]){const input=el("cap-"+key);values[key]=input.type==="checkbox"?input.checked:input.value.trim();}
  send("analyze",values);
});
el("capture-example").addEventListener("click",()=>{clear();el("capture-text").value=example;el("capture-text").focus()});
el("capture-clear").addEventListener("click",()=>{clear();el("capture-text").focus()});
window.addEventListener("pagehide",clear);
