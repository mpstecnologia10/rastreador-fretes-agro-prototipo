const byId = id => document.getElementById(id);
const brl = new Intl.NumberFormat("pt-BR", {style:"currency", currency:"BRL"});
const fold = value => value.normalize("NFD").replace(/[\u0300-\u036f]/g,"").trim().toLowerCase();
const phone = value => /^\+55\d{10,11}$/.test(value || "") ? value : null;
const dateLabel = iso => iso.split("-").reverse().join("/");
function node(tag, text, cls) {
  const n = document.createElement(tag); n.textContent = text;
  if (cls) n.className = cls;
  return n;
}
function external(label, url) {
  const a = node("a", label);
  try {const u = new URL(url); if (u.protocol !== "https:") return node("span",label); a.href = u.href;}
  catch {return node("span",label);}
  a.target = "_blank"; a.rel = "noopener noreferrer"; return a;
}
const profileKey = "fretes-agro:configuracao-caminhao:1";
function message(city) {
  const truck = byId("truck-profile").value;
  return "Olá, sou motorista autônomo"+(truck?" com "+truck:"")+". Vi no app que vocês operam em "+city+". Têm carga disponível para hoje?";
}
function waUrl(number, city) {
  const url = new URL("https://wa.me/"+number.slice(1)); url.searchParams.set("text",message(city)); return url.href;
}
export function contactActions(container, city, tel, wa) {
  const actions = node("div","","contact-actions");
  if (phone(tel)) {const a = node("a","Ligar"); a.href = "tel:"+tel; actions.append(a);}
  if (phone(wa)) {
    const a = external("Falar no WhatsApp",waUrl(wa,city));
    a.dataset.wa = wa; a.dataset.city = city; actions.append(a);
  } else {actions.append(node("small","WhatsApp empresarial não informado.","subtle"));}
  container.append(actions);
}
let selected, fuel, radar;
async function load(name) {
  const r = await fetch("data/"+name+".json",{cache:"no-cache"});
  if (!r.ok) throw new Error(name); return r.json();
}
export function updateOperations(city) {
  selected = city;
  if (!city) return;
  const place = city.nome+"/"+city.uf;
  const price = fuel?.municipios[city.ibge];
  if (fuel) {
    const line = price ? "Diesel S10 em "+place+": "+brl.format(price.media)+" (média) · Mínimo: "+brl.format(price.minimo)+" por litro" : "Sem pesquisa municipal de diesel S10 para "+place+" neste período.";
    byId("fuel-data").replaceChildren(node("strong",line),node("p","Pesquisa de "+dateLabel(fuel.inicio)+" a "+dateLabel(fuel.fim)+(price?" · "+price.postos+" postos":"")+". Não é cotação de hoje.","subtle"),external("Ver levantamento da ANP",fuel.url));
  }
  if (radar) {
    const rows = radar.companies.filter(r=>fold(r.cidade)===fold(city.nome)&&r.uf===city.uf);
    byId("regional-list").replaceChildren(...(rows.length ? rows.map(r=>{
      const card=node("article","","ops-card"); card.append(node("h3",r.nome),node("p",place+" · "+r.vinculo));
      if (r.site) card.append(external("Canal oficial",r.site));
      contactActions(card,place,r.telefone,r.whatsapp); return card;
    }) : [node("p","Nenhuma empresa com presença municipal confirmada em "+place+" no catálogo.","subtle")]));
  }
}
export function startOperations() {
  const profile = byId("truck-profile");
  try {profile.value=localStorage.getItem(profileKey)||"";} catch {}
  profile.addEventListener("change",()=>{
    try {localStorage.setItem(profileKey,profile.value);} catch {}
    for (const a of document.querySelectorAll("a[data-wa]")) a.href=waUrl(a.dataset.wa,a.dataset.city);
  });
  for (const [name,id,apply] of [
    ["fuel","fuel-data",data=>{fuel=data;updateOperations(selected);}],
    ["company_radar","regional-list",data=>{radar=data;updateOperations(selected);}],
    ["operations_directory","ops-directory",data=>{
      byId("ops-directory").replaceChildren(...data.entries.map(r=>{
        const card=node("article","","ops-card");card.append(node("small",r.categoria,"eyebrow"),node("h3",r.nome),node("span",r.custo,"pill"),node("p",r.nota),external("Abrir site oficial",r.url));return card;
      }));
    }]
  ]) load(name).then(apply).catch(()=>{byId(id).textContent="Dados indisponíveis neste momento.";});
}
