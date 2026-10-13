'use strict';
const $ = id => document.getElementById(id);
const units = ['page','email','round','hour','item'];
let review = null;
let busy = false;
let notesText = '';
function hideNotes(){$('notes-panel').hidden=true;}
const node = (tag, text, cls) => { const n=document.createElement(tag); if(text!==undefined)n.textContent=text; if(cls)n.className=cls; return n; };
function invalidate(){review=null;$('results').hidden=true;hideNotes();}
function addRow(group, data={text:'',quantity:1,unit:'item'}){
  const box=$(group); if(box.children.length>=20)return;
  const row=node('div',undefined,'row');
  const heading=node('div',undefined,'row-heading');heading.append(node('span',group==='brief'?'Deliverable':'Request'));
  const remove=node('button','Remove','remove');remove.type='button';remove.addEventListener('click',()=>{if(busy)return;row.remove();invalidate();});heading.append(remove);row.append(heading);
  const text=node('textarea');text.value=data.text;text.required=true;text.maxLength=500;text.minLength=3;
  const textLabel=node('label','Description');textLabel.append(text);row.append(textLabel);
  const quantities=node('div',undefined,'quantity');const count=node('input');count.type='number';count.min='1';count.max='1000';count.step='1';count.required=true;count.value=data.quantity;
  const countLabel=node('label',group==='brief'?'Agreed total':'Requested total');countLabel.append(count);
  const unit=node('select');for(const u of units){const option=node('option',u+'(s)');option.value=u;unit.append(option);}unit.value=data.unit;
  const unitLabel=node('label','Unit');unitLabel.append(unit);quantities.append(countLabel,unitLabel);row.append(quantities);row.addEventListener('input',invalidate);box.append(row);
}
function readRows(group){return Array.from($(group).children).map(row=>({text:row.querySelector('textarea').value,quantity:Number(row.querySelector('input').value),unit:row.querySelector('select').value}));}
function fill(data){for(const g of ['brief','requests']){$(g).replaceChildren();for(const r of data[g])addRow(g,r);}invalidate();}
$('add-brief').onclick=()=>{if(!busy){addRow('brief');invalidate();}};
$('add-request').onclick=()=>{if(!busy){addRow('requests');invalidate();}};
$('clear').onclick=()=>{if(!busy){fill({brief:[{text:'',quantity:1,unit:'item'}],requests:[{text:'',quantity:1,unit:'item'}]});$('status').textContent='Workspace cleared.';}};
$('sample').onclick=async()=>{if(busy)return;try{const res=await fetch('/sample.json');fill(await res.json());$('status').textContent='Fictional example loaded. No client data is included.';}catch{$('status').textContent='Could not load the example. Restart the app.';}};
function sourceView(candidate){const wrap=node('div',undefined,'source');wrap.append(node('p',candidate.source.id+' · '+candidate.source.quantity+' '+candidate.source.unit+'(s)','meta'),node('p',candidate.source.text),node('p','Similarity '+candidate.score.toFixed(3)+' · not a probability','meta'));return wrap;}
function showReview(data){
  $('cards').replaceChildren();
  data.results.forEach((r,i)=>{
    r.decision='Needs review';r.note='';const card=node('article',undefined,'card');card.append(node('span',r.signal,'badge'),node('h3',r.request.id+' · '+r.request.text),node('p','Requested total: '+r.request.quantity+' '+r.request.unit+'(s)','meta'),node('p',r.quantity_note,'quantity-note'),node('p','Nearest agreed deliverable','meta'),sourceView(r.candidates[0]));
    const detail=node('details');detail.append(node('summary','Compare other candidates · score gap '+r.margin.toFixed(3)));r.candidates.slice(1).forEach(c=>detail.append(sourceView(c)));card.append(detail);
    const decision=node('div',undefined,'decision');const label=node('label','My decision');const select=node('select');select.setAttribute('aria-label','My decision for '+r.request.id);for(const s of ['Needs review','Keep in agreed scope','Quote separately','Ask for clarification'])select.append(node('option',s));select.onchange=()=>{r.decision=select.value;hideNotes();};label.append(select);
    const noteLabel=node('label','My review note');const note=node('textarea');note.maxLength=1000;note.setAttribute('aria-label','My review note for '+r.request.id);note.oninput=()=>{r.note=note.value;hideNotes();};noteLabel.append(note);decision.append(label,noteLabel);card.append(decision);$('cards').append(card);
  });$('results').hidden=false;$('results-heading').focus();
}
$('review-form').onsubmit=async event=>{
 event.preventDefault();if(busy)return;invalidate();busy=true;
 for(const c of document.querySelectorAll('#review-form button,#review-form input,#review-form textarea,#review-form select,.toolbar button'))c.disabled=true;
 $('status').textContent='Comparing locally…';
 try{const response=await fetch('/api/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({brief:readRows('brief'),requests:readRows('requests')})});const data=await response.json();if(!response.ok)throw new Error(data.error||'Review failed.');review=data;showReview(data);$('status').textContent=data.results.length+' requests compared. Review each suggestion below.';}
 catch(error){$('status').textContent=error.message;}
 finally{busy=false;for(const c of document.querySelectorAll('#review-form button,#review-form input,#review-form textarea,#review-form select,.toolbar button'))c.disabled=false;}
};
function clean(text){return String(text).replaceAll('`',"'").replaceAll('\n',' ');}
$('export').onclick=()=>{
 if(!review)return;
 const lines=['# Brief Ledger review notes','','Local suggestions; reviewed decisions belong to the author. No message has been sent.','',review.notice,'','## Agreed brief',''];
 review.brief.forEach(b=>lines.push(b.id+': '+clean(b.text)+' — '+b.quantity+' '+b.unit+'(s)'));
 review.results.forEach(r=>{lines.push('','## '+r.request.id+' · '+clean(r.request.text),'','Requested total: '+r.request.quantity+' '+r.request.unit+'(s)','Signal: '+r.signal,'Quantity: '+r.quantity_note,'My decision: '+r.decision,'My note: '+(clean(r.note)||'(none)'),'', 'Candidate evidence:');r.candidates.forEach(c=>lines.push('- '+c.source.id+': '+clean(c.source.text)+' — '+c.source.quantity+' '+c.source.unit+'(s); similarity '+c.score));});
 lines.push('','Model: '+review.model+' @ '+review.revision,'Threshold: '+review.threshold+'; ambiguity margin: '+review.margin_threshold,'English only. Quantity units are entered manually. No legal interpretation or automatic quote.');
 notesText=lines.join('\n')+'\n';$('notes').value=notesText;$('notes-panel').hidden=false;$('notes').focus();
};
$('download').onclick=()=>{
 const url=URL.createObjectURL(new Blob([notesText],{type:'text/markdown'}));const a=node('a');a.href=url;a.download='brief-ledger-review.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
addRow('brief');addRow('requests');
