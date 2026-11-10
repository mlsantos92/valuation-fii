// Harness: roda as funções de cálculo do painel original (JavaScript) sobre o mesmo retrato de dados.
const fs=require("fs"),path=require("path");
const stub={innerHTML:"",textContent:"",value:"",hidden:true,classList:{toggle(){},add(){}},setAttribute(){},addEventListener(){}};
global.document={getElementById:()=>stub,querySelectorAll:()=>[],activeElement:null};
global.localStorage={getItem:()=>null,setItem(){}};
(function(){
"use strict";
const SHEET_ID="(removido)";
const SHEET_URL="https://docs.google.com/spreadsheets/d/"+SHEET_ID+"/edit";
const RANGE="'Dados Dashboard'!A1:AE700";
const SERVER="Google Sheets";
const DEF={periodo:10,cap:0.09};
// Taxas da análise de sensibilidade (como na planilha original): base 11%, otimista 0,5 p.p. abaixo, pessimista 0,5 p.p. acima
const LIQ_CUT=1e6; // corte de liquidez diária
let SENS_BASE=0.11; // taxa base da análise de sensibilidade (editável)
let SENS_TAXAS=[];
function setSensBase(b){SENS_BASE=b;SENS_TAXAS=[{k:"ot",nome:"Otimista",t:b-0.005},{k:"base",nome:"Base",t:b},{k:"pes",nome:"Pessimista",t:b+0.005}];
  document.querySelectorAll(".sens-rates").forEach(el=>el.textContent="otimista "+fP(b-0.005,1)+" · base "+fP(b,1)+" · pessimista "+fP(b+0.005,1));
  document.querySelectorAll(".sens-base-input").forEach(i=>{if(document.activeElement!==i)i.value=fN(b*100,2)})}
SENS_TAXAS=[{k:"ot",nome:"Otimista",t:0.105},{k:"base",nome:"Base",t:0.11},{k:"pes",nome:"Pessimista",t:0.115}];
// Prêmios originais da planilha: usados só se o banco do painel não estiver disponível.
const PREMIOS_PLANILHA=[{nome:"LAJES",premio:.15,modelo:.03},{nome:"SHOPPING",premio:.10,modelo:.02},{nome:"LOGÍSTICA",premio:.10,modelo:.02},{nome:"PAPEL",premio:.30,modelo:.01},{nome:"RENDA URBANA",premio:.10,modelo:.01}];
// Segmentos da Status Invest → setores da tabela de prêmios
const SEG_MAP={"LAJES CORPORATIVAS":"LAJES","SHOPPINGS":"SHOPPING","IMOVEIS INDUSTRIAIS E LOGISTICOS":"LOGÍSTICA","LOGISTICA":"LOGÍSTICA","PAPEIS":"PAPEL",
  "IMOVEIS COMERCIAIS - OUTROS":"RENDA URBANA","VAREJO":"RENDA URBANA","AGENCIAS DE BANCOS":"RENDA URBANA","MISTO":"HÍBRIDO","IMOVEIS RESIDENCIAIS":"RESIDENCIAL",
  "HOSPITALAR":"HOSPITAL","HOTEIS":"HOTEL","FUNDO DE FUNDOS":"FUNDO DE FUNDOS","FUNDO DE DESENVOLVIMENTO":"DESENVOLVIMENTO","INCORPORACOES":"DESENVOLVIMENTO",
  "FI-INFRA":"FI-INFRA","AGRICULTURA":"FIAGRO","INDEFINIDO":"NÃO CLASSIFICADO"};

const $=id=>document.getElementById(id);
const norm=s=>String(s||"").normalize("NFD").replace(/[̀-ͯ]/g,"").toUpperCase().trim();
const brl=new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL"});
const fR=v=>Number.isFinite(v)?brl.format(v):"–";
const fP=(v,d=2)=>Number.isFinite(v)?(v*100).toLocaleString("pt-BR",{minimumFractionDigits:d,maximumFractionDigits:d})+"%":"–";
const fN=(v,d=2)=>Number.isFinite(v)?v.toLocaleString("pt-BR",{minimumFractionDigits:d,maximumFractionDigits:d}):"";
const fBig=v=>{if(!Number.isFinite(v))return"–";if(v>=1e9)return"R$ "+fN(v/1e9,1)+" bi";if(v>=1e6)return"R$ "+fN(v/1e6,1)+" mi";if(v>=1e3)return"R$ "+fN(v/1e3,0)+" mil";return fR(v)};
function parseBR(raw){
  if(raw==null)return NaN; if(typeof raw==="number")return raw;
  let s=String(raw).trim(); if(!s||s==="-")return NaN;
  const pct=s.includes("%"); s=s.replace(/[^\d,.\-]/g,"");
  if(s.includes(",")){s=s.replace(/\./g,"").replace(",",".")}
  else if((s.match(/\./g)||[]).length>1){s=s.replace(/\./g,"")}
  const n=parseFloat(s); return pct?n/100:n;
}
const pctIn=s=>{const n=parseBR(s);return Number.isFinite(n)?n/100:NaN};
function esc(s){return String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}

// ---------- Estado ----------
const S={
  funds:new Map(), fundsOrder:[], dataState:"loading", lastRead:null, tradeTime:"",
  premios:null, premiosVer:false, tesouro:{ipca:{nome:"Tesouro IPCA+ 2032",taxa:NaN},pre:{nome:"Tesouro Prefixado 2029",taxa:NaN},atualizadoEm:"",fonte:""},
  overrides:{}, sel:"TRXF11", sc:"base", db:null, canWrite:true, autoAdded:false,
  expSort:{k:"liq",dir:-1}, sensSort:{k:"tk",dir:1}, sensSt:new Set(), favs:new Set(), favPath:null, hideLow:false, pvpLow:false, pvpHigh:false, soSaude:false, saude:{}, bestOpp:false, oppTipos:new Set(["FII"])
};
try{const t=localStorage.getItem("vfii.sel");if(t)S.sel=t}catch(e){}

// ---------- Cálculo ----------
function taxaBasicaTesouro(){const a=S.tesouro.ipca.taxa,b=S.tesouro.pre.taxa;return(Number.isFinite(a)&&Number.isFinite(b))?(a+b)/2:NaN}
function setorDe(tk){const o=S.overrides[tk]||{};if(o.setor)return o.setor;const f=S.funds.get(tk);return f?setorAuto(f):""}
// Fundo marcado como FIAGRO ou FI-INFRA em qualquer fonte: vale a categoria de maior risco (maior prêmio)
function setorAuto(f){
  const flags=String(f.cat||"").split(";").map(x=>x.trim());
  const base=f.pred||anbSetor(f)||setorDoSeg(f.seg); const cands=[];
  if(flags.includes("FIAGRO"))cands.push("FIAGRO");
  if(flags.includes("FI-INFRA"))cands.push("FI-INFRA");
  if(!cands.length)return base;
  if(base&&!["NÃO CLASSIFICADO","OUTROS"].includes(norm(base)==="NAO CLASSIFICADO"?"NÃO CLASSIFICADO":base))cands.push(base);
  let best=cands[0],bp=-1; cands.forEach(c=>{const pr=premioDe(c);if(Number.isFinite(pr)&&pr>bp){bp=pr;best=c}}); return best;
}
// Segmento ANBIMA (Funds Explorer) como classificação principal dos FIIs.
// Fundos de papel (Papéis/FOF na Status Invest) mantêm a Status Invest; fundos de tijolo usam a ANBIMA; sem ANBIMA, Status Invest.
const ANB_MAP={"SHOPPINGS":"SHOPPING","LAJES CORPORATIVAS":"LAJES","RESIDENCIAL":"RESIDENCIAL","HIBRIDO":"HÍBRIDO","TITULOS E VALORES MOBILIARIOS":"PAPEL","LOGISTICA":"LOGÍSTICA","HOTEL":"HOTEL","HOSPITAL":"HOSPITAL"};
function anbSetor(f){const a=ANB_MAP[norm(f.anb)];if(!a)return"";const si=norm(f.seg);
  if(si==="PAPEIS"||si==="FUNDO DE FUNDOS")return""; // fundo de papel: mantém a classificação da Status Invest
  return a}
function tipoDe(tk){const s=norm(setorDe(tk));return s==="FIAGRO"?"FIAGRO":s==="FI-INFRA"?"FI-INFRA":"FII"}
function setorDoSeg(seg){const n=norm(seg);if(!n)return"";return SEG_MAP[n]||String(seg).toUpperCase().trim()}
function premioDe(setor){const list=S.premios||PREMIOS_PLANILHA;const r=list.find(p=>norm(p.nome)===norm(setor));return r?r.premio:NaN}
const RISCO_DEF={on:true,vacMin:0.05,vacPP:1,vacMax:0.20,hy1:0.02,hyPen1:0,hy2:0.05,hyPen2:0,atPen:0.10,setoresHY:["PAPEL"],hcOn:true,hcK:1,setorNoRank:true};
function RK(){return Object.assign({},RISCO_DEF,S.riscoCfg||{})}
let _medHY={t:0,v:NaN};
function medDYPapel(){const now=Date.now();if(now-_medHY.t<3000)return _medHY.v;const c=RK();const a=[];S.funds.forEach((f,tk)=>{if(f.excl||!Number.isFinite(f.dy)||f.dy<=0||f.dy>0.4)return;if(c.setoresHY.includes(norm(setorDe(tk))))a.push(f.dy)});a.sort((x,y)=>x-y);const n=a.length;_medHY={t:now,v:n?(n%2?a[(n-1)/2]:(a[n/2-1]+a[n/2])/2):NaN};return _medHY.v}
function riscoFundo(tk,f,setor){const c=RK();const r={vac:0,hy:0,at:0,total:0,vacP:NaN,spread:NaN,notas:[]};if(!c.on)return r;
  const sd=S.saude&&S.saude[tk];
  if(sd&&Number.isFinite(sd.vacP)){r.vacP=sd.vacP;if(sd.vacP>c.vacMin){r.vac=Math.min(c.vacMax,(sd.vacP-c.vacMin)*c.vacPP);r.notas.push("vacância "+fP(sd.vacP,1))}}
  if(c.setoresHY.includes(norm(setor))&&Number.isFinite(f.dy)){const m=medDYPapel();if(Number.isFinite(m)){r.spread=f.dy-m;if(r.spread>c.hy2){r.hy=c.hyPen2;r.notas.push("DY "+fP(r.spread,1)+" acima da mediana do papel")}else if(r.spread>c.hy1){r.hy=c.hyPen1;r.notas.push("DY "+fP(r.spread,1)+" acima da mediana do papel")}}}
  if(sd&&sd.n==="at"){r.at=c.atPen;r.notas.push("saúde em Atenção")}
  r.total=r.vac+r.hy+r.at;return r}
// Haircut de rendimento: média mensal dos últimos 12 meses (inclui o pagamento extra anual da regra dos 95%) menos 1 desvio padrão dos pagamentos regulares.
function taxaRank(p,t){const c=RK();const pr=c.setorNoRank?(Number.isFinite(p.premio)?p.premio:(p.rk?p.rk.total:0)):(p.rk?p.rk.total:0);return t*(1+pr)}
function haircut(tk,f,divNorm,preco){const c=RK();const r={div:divNorm,base:divNorm,sd:0,fonte:"último rendimento",n:0,extra:NaN};
  const aj=S.divAj&&S.divAj[tk]; if(aj&&aj.fixo&&Number.isFinite(aj.div)){r.div=aj.div;r.base=aj.div;r.fonte="rendimento recorrente conferido no gestor ("+aj.motivo+")";return r}
  if(!c.hcOn)return r;
  const h=S.hist&&S.hist[tk]; const v=Array.isArray(h)?h.filter(x=>Number.isFinite(x)&&x>0).slice(0,12):[];
  if(v.length>=6){const soma=v.reduce((a,b)=>a+b,0);r.base=soma/v.length;r.n=v.length;
    const srt=[...v].sort((a,b)=>a-b),n=srt.length,med=n%2?srt[(n-1)/2]:(srt[n/2-1]+srt[n/2])/2;r.med=med;
    // pagamentos acima da mediana = extra (regra dos 95%, resultados não recorrentes); o desvio mede só a oscilação até a mediana
    r.extraMes=Math.max(0,r.base-med);r.nExtra=v.filter(x=>x>med+1e-9).length;
    const reg=v.map(x=>Math.min(x,med));const m=reg.reduce((a,b)=>a+b,0)/reg.length;r.sd=Math.sqrt(reg.reduce((a,b)=>a+(b-m)*(b-m),0)/Math.max(1,reg.length-1));
    r.div=Math.max(0,r.base-c.hcK*r.sd);r.fonte="mediana "+fR(med)+" + extra "+fR(r.extraMes)+"/mês − "+c.hcK+" desvio padrão";return r}
  if(Number.isFinite(f.dySI)&&f.dySI>0&&f.dySI<=0.4&&Number.isFinite(preco)&&preco>0){r.base=f.dySI*preco/12;r.div=r.base;r.fonte="DY 12m da Status Invest ÷ 12 (sem histórico para o desvio padrão)";return r}
  return r}
function premissas(tk){
  const f=S.funds.get(tk)||{}; const o=S.overrides[tk]||{};
  const preco=Number.isFinite(f.live)?f.live:(Number.isFinite(f.cot)?f.cot:(Number.isFinite(o.precoManual)?o.precoManual:NaN));
  const divAuto=Number.isFinite(f.ud)&&f.ud>0?f.ud:((Number.isFinite(f.dy)&&Number.isFinite(f.cot))?f.dy*f.cot/12:NaN);
  const aj=S.divAj&&S.divAj[tk]; const divNorm=aj&&Number.isFinite(aj.div)&&aj.div>0?aj.div:divAuto;
  const hc=haircut(tk,f,divNorm,preco); const div=hc.div;
  const setor=setorDe(tk); const premioSetor=premioDe(setor);
  const rk=riscoFundo(tk,f,setor); const premio=Number.isFinite(premioSetor)?Math.max(premioSetor,rk.total):(rk.total>0?rk.total:premioSetor);
  const base=taxaBasicaTesouro();
  return{preco,div,divAuto,divNorm,hc,aj:aj||null,setor,premio,premioSetor,rk,base,periodo:Number.isFinite(o.periodo)?o.periodo:DEF.periodo,cap:Number.isFinite(o.cap)?o.cap:DEF.cap,
    taxa:base*(1+(Number.isFinite(premio)?premio:0)),f,o};
}
function fluxo(div,taxa,periodo,cap){
  const anual=div*12, n=Math.max(1,Math.round(periodo)); const rows=[]; let total=0;
  const exit=anual/cap;
  for(let y=1;y<=n;y++){const renda=y===n?anual+exit:anual;const vp=renda/Math.pow(1+taxa,y);total+=vp;rows.push({y,renda,vp,exitVp:y===n?exit/Math.pow(1+taxa,y):0})}
  return{rows,total,exit,anual};
}
function cenarios(p){
  return{base:fluxo(p.div,p.taxa,p.periodo,p.cap),ot:fluxo(p.div,p.taxa,p.periodo,p.cap-0.005),pes:fluxo(p.div,p.taxa,p.periodo,p.cap+0.005)};
}
function ingest(values){
  if(!Array.isArray(values)||!values.length){S.dataState="empty";return}
  const head=values[0].map(norm);
  if(head[0]&&head[0].startsWith("#")){S.dataState="needsAccess";return}
  const ix=n=>head.findIndex(h=>h===n||h.startsWith(n));
  const c={tk:ix("PAPEL"),seg:ix("SEGMENTO"),cot:ix("COTACAO"),ud:ix("ULTIMO DIVIDENDO"),dy:ix("DIVIDEND YIELD"),pvp:ix("P/VP"),vm:ix("VALOR DE MERCADO"),liq:ix("LIQUIDEZ"),cr:ix("CAP RATE"),vac:ix("VACANCIA"),live:ix("PRECO B3"),cat:ix("CATEGORIA"),siTipo:ix("TIPO STATUS INVEST"),pred:ix("SETOR PREDOMINANTE"),anb:ix("SEGMENTO ANBIMA"),divSI:ix("DIV STATUS INVEST"),dySI:ix("DY STATUS INVEST"),excl:ix("EXCLUSAO")};
  if(c.tk<0){S.dataState="needsAccess";return}
  const tt=values[1]&&values[1][16]; if(tt)S.tradeTime=String(tt);
  const ld=values[1]&&values[1][15]; if(ld)S.listDate=String(ld);
  const m=new Map();
  for(let i=1;i<values.length;i++){
    const r=values[i]; const tk=String(r[c.tk]||"").toUpperCase().trim();
    if(!/^[A-Z0-9]{4}1[1-5]B?$/.test(tk))continue;
    const liq=parseBR(r[c.liq]); const live=c.live>=0?parseBR(r[c.live]):NaN;
    if(!(liq>0)&&!Number.isFinite(live))continue; // sem negócios na B3: fora (balcão/sem liquidez)
    let dy=parseBR(r[c.dy]); if(Number.isFinite(dy)&&dy>1)dy=dy/100;
    let cr=parseBR(r[c.cr]); if(Number.isFinite(cr)&&cr>1)cr=cr/100;
    let vac=parseBR(r[c.vac]); if(Number.isFinite(vac)&&vac>1)vac=vac/100;
    m.set(tk,{tk,seg:String(r[c.seg]||"").trim(),cot:parseBR(r[c.cot]),ud:c.ud>=0?parseBR(r[c.ud]):NaN,cat:c.cat>=0?String(r[c.cat]||"FII").trim().toUpperCase():"FII",siTipo:c.siTipo>=0?String(r[c.siTipo]||"").trim().toUpperCase():"",pred:c.pred>=0?String(r[c.pred]||"").trim().toUpperCase():"",anb:c.anb>=0?String(r[c.anb]||"").trim():"",excl:c.excl>=0?String(r[c.excl]||"").trim():"",divSI:c.divSI>=0&&String(r[c.divSI]||"")!==""?parseFloat(r[c.divSI]):NaN,dySI:c.dySI>=0&&String(r[c.dySI]||"")!==""?parseFloat(r[c.dySI])/100:NaN,dy,pvp:parseBR(r[c.pvp]),vm:parseBR(r[c.vm]),liq,cr,vac,live});
  }
  if(!m.size){S.dataState="needsAccess";return}
  S.funds=m; S.fundsOrder=[...m.keys()].sort(); S.dataState="live";
  const dl=$("tickers"); dl.innerHTML=S.fundsOrder.map(t=>'<option value="'+t+'"></option>').join("");
}
function sensOf(tk){
  const p=premissas(tk), f=p.f;
  const ok=Number.isFinite(p.div)&&p.div>0&&p.cap>0.006&&Number.isFinite(p.preco)&&p.preco>0;
  const r={rkAj:p.rk?p.rk.total:0,rkNotas:p.rk?p.rk.notas.join("; "):"",tk,cat:tipoDe(tk),setor:setorDe(tk)||"SEM SETOR",seg:f.seg||"",preco:p.preco,div:p.div,dy:f.dy,pvp:f.pvp,liq:f.liq,cap:p.cap,fav:S.favs.has(tk)?1:0,vmin:NaN,vbase:NaN,vmax:NaN,st:"na",desc:NaN,vsBase:NaN,pos:NaN};
  if(!ok)return r;
  const vals=[];[-.005,0,.005].forEach(dc=>SENS_TAXAS.forEach(x=>vals.push(fluxo(p.div,taxaRank(p,x.t),p.periodo,p.cap+dc).total)));
  r.vmin=Math.min(...vals); r.vmax=Math.max(...vals); r.vbase=vals[4];
  r.st=p.preco<r.vmin?"below":(p.preco>r.vmax?"above":"inside");
  // Conferência com a Status Invest (backtest dos dados de entrada)
  const why=[]; const dChk=p.divNorm; const yAnual=dChk*12/p.preco;
  r.dyZero=!(f.dy>0)||(Number.isFinite(f.dySI)&&f.dySI<=0);
  if(r.dyZero)why.push("DY 12m zerado");
  if(Number.isFinite(f.pvp)&&f.pvp>1.5)why.push("P/VP "+f.pvp.toFixed(2).replace(".",",")+" muito acima de 1, incompatível com desconto no fluxo");
  {const dyx=Math.max(Number.isFinite(f.dySI)?f.dySI:0,Number.isFinite(f.dy)?f.dy:0);if(dyx>0.25&&!(f.dySI>0.4))why.push("DY 12m de "+fP(dyx,0)+" sugere rendimento não recorrente");}
  if(Number.isFinite(f.dySI)&&f.dySI>0.4)why.push("DY 12m irreal na Status Invest ("+fP(f.dySI,0)+")");
  if(Number.isFinite(f.divSI)&&f.divSI>0&&Math.abs(dChk-f.divSI)/f.divSI>0.25)why.push("rendimento "+fR(dChk)+" ≠ Status Invest "+fR(f.divSI));
  if(Number.isFinite(f.dySI)&&f.dySI>0&&f.dySI<=0.4&&yAnual>f.dySI*1.5&&yAnual-f.dySI>0.04)why.push("rendimento atual anualizado "+fP(yAnual,1)+" muito acima do DY 12m "+fP(f.dySI,1));
  r.chk=why.length?"bad":(Number.isFinite(f.divSI)||Number.isFinite(f.dySI)?"ok":"na"); r.chkWhy=why.join("; ");
  r.desc=r.vmin/p.preco-1; r.vsBase=r.vbase/p.preco-1; r.over=p.preco/r.vmax-1;
  r.pos=(p.preco-r.vmin)/(r.vmax-r.vmin);
  return r;
}
function isExcl(tk){const f=S.funds.get(tk);return!!(f&&f.excl)}
function nExcl(){let n=0;S.funds.forEach((f,tk)=>{if(f.excl)n++});return n}
function isSusp(tk){const p=premissas(tk);const liq=p.f.liq;if(p.f.excl)return false;return!(Number.isFinite(p.div)&&p.div>0&&Number.isFinite(p.preco)&&p.preco>0)||p.div/p.preco>0.04||liq>5e8}
function nSusp(){let n=0;S.funds.forEach((f,tk)=>{if(!f.excl&&isSusp(tk))n++});return n}

const RAW=path.join(__dirname,"..","..","data","raw");
const J=n=>JSON.parse(fs.readFileSync(path.join(RAW,n),"utf8"));
function csv(t){const out=[];let row=[],f="",q=false;for(let i=0;i<t.length;i++){const c=t[i];if(q){if(c=='"'){if(t[i+1]=='"'){f+='"';i++}else q=false}else f+=c}else if(c=='"')q=true;else if(c==","){row.push(f);f=""}else if(c=="\n"){row.push(f);out.push(row);row=[];f=""}else if(c!="\r")f+=c}if(f||row.length){row.push(f);out.push(row)}return out}
const values=csv(fs.readFileSync(process.env.CSV_PLANILHA||path.join(RAW,"fiis_planilha.csv"),"utf8"));
S.premios=J("premios_risco.json").setores; S.premiosVer=true;
const tes=J("tesouro.json"); S.tesouro={...S.tesouro,...tes};
S.hist=J("rendimentos_12m.json").fundos; S.saude=J("saude_fundos.json").fundos; S.divAj=J("ajustes_rendimento.json").fundos;
S.overrides=J("premissas_fundos.json");
ingest(values);
const out={};
S.funds.forEach((f,tk)=>{const susp=!f.excl&&isSusp(tk);const r=(!f.excl&&!susp)?sensOf(tk):null;const p=premissas(tk);
  out[tk]={setor:setorDe(tk),tipo:tipoDe(tk),div:p.div,taxa:p.taxa,premio:p.premio,excl:!!f.excl,susp,vmin:r?r.vmin:null,vbase:r?r.vbase:null,vmax:r?r.vmax:null,st:r?r.st:null,chk:r?r.chk:null,dyZero:r?r.dyZero:null}});
fs.writeFileSync(process.env.SAIDA||path.join(__dirname,"resultado_painel_original.json"),JSON.stringify(out));
console.log(Object.keys(out).length+" fundos calculados pelo painel original");
})();
