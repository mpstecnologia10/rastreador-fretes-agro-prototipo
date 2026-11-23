/* No application network operations after boot. Payload stays in this worker. */
const here=new URL("../runtime/",self.location.href);
const data=new URL("../data/municipios.json",self.location.href);
let init;
async function boot(){
  importScripts(new URL("pyodide.js",here).href);
  const py=await loadPyodide({indexURL:here.href});
  py.FS.mkdir("/home/pyodide/pipeline");
  await Promise.all(["__init__.py","domain.py","capture.py"].map(async name=>{
    const response=await fetch(new URL(name,here));
    if(!response.ok)throw new Error();
    py.FS.writeFile("/home/pyodide/pipeline/"+name,await response.text());
  }));
  const cities=await fetch(data);
  if(!cities.ok)throw new Error();
  const catalog=await cities.text();
  py.globals.set("cities_json",catalog);
  py.runPython(`
import json
from datetime import date
from pipeline.domain import Cities
from pipeline.capture import parse, analyze
_rows = json.loads(cities_json)
_cities = Cities(_rows["hubs"], _rows["official"])
def _run(action, raw):
    args = json.loads(raw)
    today = date.fromisoformat(args["today"])
    if action == "parse":
        return json.dumps(parse(args["value"], _cities, today))
    return json.dumps(analyze(args["value"], _cities, today))
`);
  const municipalities=JSON.parse(catalog);
  const states={"51":"MT","52":"GO","50":"MS","41":"PR","35":"SP","31":"MG","15":"PA","43":"RS"};
  const list=municipalities.official.map(c=>({id:c.id,label:c.nome+"/"+states[c.id.slice(0,2)]}));
  self.postMessage({cities:list});
  return py.globals.get("_run");
}
self.onmessage=async ({data:{action,value,today,id}})=>{
  try{
    const run=await (init??=boot());
    self.postMessage({id,action,result:JSON.parse(run(action,JSON.stringify({value,today})))});
  }catch{self.postMessage({id,error:true});}
};
