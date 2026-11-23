const box = document.querySelector("#editais");
try {
  const response = await fetch("data/editais.json", {cache:"no-store"});
  if (!response.ok) throw Error();
  const snapshot = await response.json();
  function render(){
    const now = Date.now();
    const valid = snapshot.editais.filter(r => Date.parse(r.expires_at)>now &&
      now-Date.parse(r.last_seen_at)<86400000 && /^https:\/\/pncp\.gov\.br\/app\/editais\/\d{14}\/\d{4}\/\d+$/.test(r.fonte));
    box.replaceChildren();
    for(const r of valid){
      const p=document.createElement("p"), a=document.createElement("a");
      a.href=r.fonte; a.textContent="Consultar edital no PNCP";
      p.append(r.municipio_comprador+"/"+r.uf+" — "+r.objeto+" · Prazo: "+
        new Intl.DateTimeFormat("pt-BR",{dateStyle:"short",timeStyle:"short",timeZone:"America/Sao_Paulo"}).format(new Date(r.expires_at))+" (Brasília). ",a);
      box.append(p);
    }
    if(valid.length && snapshot.errors?.length)box.append("Consulta parcial. Somente editais confirmados nas últimas 24 horas.");
    if(!valid.length) box.textContent=snapshot.errors?.length?"Consulta incompleta; nenhum edital vigente confirmado nesta amostra.":"Nenhum edital vigente confirmado nesta amostra.";
  }
  render(); setInterval(render,60000);
}catch{box.textContent="Consulta de editais indisponível.";}
