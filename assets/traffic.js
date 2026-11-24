// O mapa só conecta ao provedor depois de um toque. O tempo é sempre da
// observação, nunca do deploy nem da última vez que o motorista abriu a tela.
const node=(tag, label)=>Object.assign(document.createElement(tag),{textContent:label});
const outside=(title,href)=>Object.assign(node("a",title),{href,target:"_blank",rel:"noopener noreferrer"});

export function reading(t, now=Date.now()){
  const age=now-Date.parse(t.observado_em), level=t.jam_level;
  if(!(age>=0 && age<=900000 && Number.isInteger(level) && level>=0 && level<=5))
    return "⚪ Sem medição recente";
  return level===0?"🟢 Fluxo normal":level<=2?"🟡 Lentidão":level===5?"🔴 Via bloqueada":"🔴 Congestionamento intenso";
}

async function start(){
  const box=document.getElementById("traffic-list");
  if(!box)return;
  const response=await fetch("data/terminal_traffic.json",{cache:"no-cache"});
  if(!response.ok)throw new Error();
  const data=await response.json(), readings=[];
  box.replaceChildren();
  for(const t of data.terminais){
    const card=node("article","");card.className="card";
    const status=node("strong",reading(t));readings.push([t,status]);
    const actions=node("div","");actions.className="link-list";
    const button=node("button","Ver trânsito no mapa");button.type="button";button.setAttribute("aria-expanded","false");
    const target=node("div","");
    const map=new URL("https://embed.waze.com/iframe");
    map.search=new URLSearchParams({lat:t.lat,lon:t.lon,zoom:14,pin:1});
    const external=new URL("https://www.waze.com/live-map/");
    external.search=new URLSearchParams({latlng:t.lat+","+t.lon,zoom:14});
    button.addEventListener("click",()=>{
      if(target.childElementCount){
        target.replaceChildren();button.textContent="Ver trânsito no mapa";button.setAttribute("aria-expanded","false");return;
      }
      const frame=document.createElement("iframe");
      Object.assign(frame,{src:map.href,title:"Mapa de trânsito no entorno de "+t.nome+", "+t.cidade,height:"320",width:"100%",referrerPolicy:"no-referrer"});
      target.append(frame);button.textContent="Fechar mapa";button.setAttribute("aria-expanded","true");
    });
    actions.append(button,outside("Abrir no Waze",external.href));
    card.append(node("h3",t.nome),node("p",t.cidade),status);
    if(t.observado_em)card.append(node("p","Última leitura Waze: "+new Date(t.observado_em).toLocaleString("pt-BR")));
    card.append(actions,target,outside("Referência do terminal",t.fonte_local));box.append(card);
  }
  const refresh=()=>{for(const [t,s] of readings)s.textContent=reading(t);};
  setInterval(refresh,30000);document.addEventListener("visibilitychange",refresh);
}
start().catch(()=>{const box=document.getElementById("traffic-list");if(box)box.textContent="Não foi possível carregar os pontos de consulta.";});
