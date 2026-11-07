import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const path = new URL('../deployment/web-console/static/app.js', import.meta.url);
async function load() { let source = ''; try { source = await readFile(path, 'utf8'); } catch {} return import('data:text/javascript;base64,' + Buffer.from(source).toString('base64')); }
function fixture({hash='',denied=false}={}) {
 class Element extends EventTarget {
  dataset={}; value=''; hidden=true; disabled=false; textContent=''; handlers={};
  addEventListener(type,fn){(this.handlers[type]??=[]).push(fn);super.addEventListener(type,fn)}
  setAttribute(k,v){this[k]=v} blur(){} focus(){} async emit(type){await Promise.all((this.handlers[type]||[]).map(fn=>fn({preventDefault(){}})))}
 }
 const ids=['screen','phone-input','status','message','remaining','phone-keyboard','keyboard-toggle','zoom','reconnect','logout'];
 const nodes=Object.fromEntries(ids.map(id=>[id,new Element()]));const calls=[],rfbs=[];let interval;
 const env={location:{hash,pathname:'/ea-console/',search:'',href:'https://api.nevstore.id:8443/ea-console/'+hash},history:{replaceState(){calls.push('scrub')}},document:{getElementById:id=>nodes[id],body:{dataset:{}},querySelectorAll:()=>[]},
 fetch:async(url,options)=>{calls.push({url,options});return {ok:!denied,status:denied?401:200,json:async()=>url.endsWith('connection')?{password:'synthetic-vnc-only',expires_at:Date.now()+60000}:{expires_at:Date.now()+60000}}},
 setInterval(fn){interval=fn;return 1},clearInterval(){},loadRFB:async()=>({default:class extends Element{constructor(screen,url,options){super();this.url=url;this.options=options;rfbs.push(this)}disconnect(){this.stopped=true}sendKey(){} }} )};
 return {env,nodes,calls,rfbs,tick:()=>interval?.()};
}
test('one-use exchange precedes private connection; reconnect uses cookie; logout disconnects',async()=>{
 const {boot}=await load();const f=fixture({hash:'#ticket='+'t'.repeat(43)});await boot(f.env);
 assert.equal(f.calls[0],'scrub');const api=f.calls.filter(c=>c.url);assert.deepEqual(api.map(c=>c.url),['./api/session','./api/connection']);
 assert.equal(api[0].options.method,'POST');assert.equal(api[0].options.headers['X-EA-Console'],'1');assert.equal(api[0].options.credentials,'same-origin');
 assert.equal(api[1].options.method,'POST','credential request must use POST so a real browser sends Origin');
 assert.equal(f.rfbs[0].url,'wss://api.nevstore.id:8443/ea-console/ws');assert.equal(f.rfbs[0].resizeSession,false);assert.equal(f.rfbs[0].scaleViewport,true);
 await f.rfbs[0].emit('connect');assert.equal(f.nodes.screen.dataset.status,'true');
 await f.nodes.zoom.emit('click');assert.equal(f.rfbs[0].clipViewport,true);assert.equal(f.rfbs[0].dragViewport,true);
 await f.nodes.reconnect.emit('click');assert.equal(f.calls.filter(c=>c.url==='./api/session').length,1);
 await f.nodes.logout.emit('click');assert.equal(f.nodes.screen.dataset.status,'false');assert.ok(f.rfbs.at(-1).stopped);assert.equal(f.calls.at(-1).url,'./api/logout');assert.equal(f.calls.at(-1).options.method,'POST');
 assert.doesNotMatch(JSON.stringify(f.nodes),/synthetic-vnc-only|tttttttttttt/);
});
test('expiry clears input and disconnects without a further request',async()=>{
 const {boot}=await load();const f=fixture();await boot(f.env);await f.rfbs[0].emit('connect');f.nodes['phone-input'].value='synthetic-draft';
 const now=Date.now;const count=f.calls.length;try{Date.now=()=>now()+120000;f.tick()}finally{Date.now=now}
 assert.equal(f.nodes['phone-input'].value,'');assert.equal(f.nodes.screen.dataset.status,'false');assert.equal(f.nodes.reconnect.disabled,true);assert.ok(f.rfbs[0].stopped);assert.equal(f.calls.length,count);
});
test('cookie resume uses GET and denied session never imports RFB',async()=>{
 const {boot}=await load();const f=fixture({denied:true});await boot(f.env);
 assert.equal(f.calls[0].url,'./api/session');assert.equal(f.calls[0].options.method,undefined);assert.equal(f.rfbs.length,0);assert.match(f.nodes.message.textContent,/link privat baru/);assert.equal(f.nodes.reconnect.disabled,true);
});
test('IME final insertFromComposition does not resend committed text', async()=>{
 const {bindPhoneInput}=await load();const input=new EventTarget();input.value='';const sent=[];bindPhoneInput(input,s=>sent.push(s));
 const fire=(type,props={})=>{const e=new Event(type,{cancelable:true});Object.assign(e,props);input.dispatchEvent(e)};
 fire('compositionstart');input.value='中';fire('compositionend');input.value='中';fire('input',{inputType:'insertFromComposition'});
 assert.deepEqual(sent,[0x01004e2d]);assert.equal(input.value,'');
});
test('session UI contract, private assets and no persistent sensitive channels', async () => {
 const source=await readFile(path,'utf8');
 assert.match(source,/export async function boot/);
 assert.doesNotMatch(source,/localStorage|sessionStorage|console\.(log|debug)|clipboardPasteFrom|sendCtrlAltDel/);
 const html=await readFile(new URL('../deployment/web-console/static/index.html',import.meta.url),'utf8');
 assert.match(html,/Trading OFF — login demo saja/);assert.match(html,/type="password"/);assert.doesNotMatch(html,/<form|<input[^>]*\sname="/);
 assert.match(source,/X-EA-Console/);assert.match(source,/credentials: 'same-origin'/);assert.match(source,/\.\/vendor\/core\/rfb.js/);assert.match(source,/resizeSession = false/);assert.match(source,/clipViewport/);
});
test('phone input clears immediately, IME commits once, deletion and Enter do not duplicate', async () => {
 const {bindPhoneInput} = await load(); assert.equal(typeof bindPhoneInput,'function');
 const input = new EventTarget(); input.value = ''; const sent=[];
 bindPhoneInput(input,(sym)=>sent.push(sym));
 const fire=(type,props={})=>{const e=new Event(type,{cancelable:true});Object.assign(e,props);input.dispatchEvent(e);};
 input.value='é';fire('input');assert.equal(input.value,'');assert.deepEqual(sent,[233]);
 fire('compositionstart');input.value='中';fire('input',{isComposing:true});assert.deepEqual(sent,[233]);fire('compositionend',{data:'中'});fire('input');assert.deepEqual(sent,[233,0x01004e2d]);assert.equal(input.value,'');
 fire('keydown',{key:'Backspace'});fire('keydown',{key:'Enter'});assert.deepEqual(sent.slice(-2),[0xff08,0xff0d]);
 fire('beforeinput',{inputType:'deleteContentBackward'});assert.equal(sent.at(-1),0xff08);
});
test('Unicode, Latin1, newline and control key conversion', async () => {
 const {textKeysyms,controlKeysyms} = await load();
 assert.equal(typeof textKeysyms,'function');
 assert.deepEqual(textKeysyms('Aé中😀\r\n\t\b\u0000'),[65,233,0x01004e2d,0x0101f600,0xff0d,0xff09,0xff08]);
 assert.deepEqual(controlKeysyms('selectAll'),[[0xffe3,true],[97,true],[97,false],[0xffe3,false]]);
 assert.deepEqual(controlKeysyms('Escape'),[[0xff1b,true],[0xff1b,false]]);
});
test('ticket removed synchronously before any network, strict one-use format', async () => {
 const {consumeTicket, websocketURL} = await load();
 assert.equal(typeof consumeTicket, 'function');
 const events = []; const ticket = 'a'.repeat(43);
 const loc = {hash:'#ticket='+ticket, pathname:'/ea-console/', search:''};
 assert.equal(consumeTicket(loc, {replaceState(...args){events.push(args)}}), ticket);
 assert.deepEqual(events, [[null,'','/ea-console/']]);
 for(const hash of ['#abc','#ticket=short','#ticket='+ticket+'&x=1','#ticket='+ticket+'!']) assert.equal(consumeTicket({...loc,hash},{replaceState(){}}),null);
 assert.equal(websocketURL('https://api.nevstore.id:8443/ea-console/?secret=no#bad'),'wss://api.nevstore.id:8443/ea-console/ws');
});
