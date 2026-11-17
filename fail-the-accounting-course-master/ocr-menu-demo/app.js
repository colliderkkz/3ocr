/* 食单识别：无需构建工具的交互演示。自有图片只做图文校验，OCR 文本由用户粘贴。 */
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const xmlEsc = esc;
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; };
const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`);
const defaultStores = ['春熙路·小满食堂','高新·禾木小馆','锦江·晚风里'];
const seed = [
  {name:'招牌热菜',price:'',category:'',type:'header',confidence:.98,match:1,status:'verified',box:1,imageIndex:0},
  {name:'宫保鸡丁',price:'38',category:'热菜',type:'dish',confidence:.96,match:.95,status:'verified',box:2,imageIndex:0},
  {name:'麻婆豆腐',price:'28',category:'热菜',type:'dish',confidence:.94,match:.93,status:'verified',box:3,imageIndex:0},
  {name:'水煮鱼',price:'68',category:'热菜',type:'dish',confidence:.88,match:.82,status:'pending',box:4,imageIndex:0},
  {name:'红烧肉',price:'',category:'热菜',type:'dish',confidence:.72,match:.61,status:'pending',box:5,imageIndex:0},
  {name:'汤羹小食',price:'',category:'',type:'header',confidence:.97,match:1,status:'verified',box:1,imageIndex:1},
  {name:'酸辣汤',price:'18',category:'汤品',type:'dish',confidence:.91,match:.88,status:'pending',box:2,imageIndex:1},
  {name:'宫保鸡丁',price:'38',category:'热菜',type:'dish',confidence:.89,match:.85,status:'pending',box:3,imageIndex:1}
];
function sampleBatch() {
  const images = [{id:'sample-1',name:'小满食堂菜单 01',status:'sample',angle:0,ocrText:''},{id:'sample-2',name:'小满食堂菜单 02',status:'sample',angle:0,ocrText:''}];
  return {id:'sample',store:defaultStores[0],date:today(),mode:'sample',done:false,images,records:seed.map((r,i)=>({ ...r,id:i+1,imageId:images[r.imageIndex].id,sourceIds:[images[r.imageIndex].id],duplicateIgnored:false }))};
}
const storageKey = 'menuDemoV2';
let state;
try { state = JSON.parse(localStorage.getItem(storageKey)); } catch { state = null; }
if (!state || !Array.isArray(state.batches)) state = {stores:[...defaultStores],batches:[sampleBatch()],activeBatchId:'sample'};
if (!state.batches.length) { state.batches.push(sampleBatch()); state.activeBatchId='sample'; }
let currentPhoto=0, activeId=null, editingId=null, filterMode='all', selectedFiles=[], currentView='verify', zoom=1, toastTimer, imageCache=new Map();
const batch = () => state.batches.find(b=>b.id===state.activeBatchId) || state.batches[0];
const image = () => batch().images[currentPhoto];
const records = () => batch().records;
function persist() { try { localStorage.setItem(storageKey,JSON.stringify(state)); } catch { toast('浏览器存储空间不足，请先导出数据'); } }
function toast(message) { const t=$('toast'); t.textContent=message;t.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.classList.remove('show'),3200); }
function issue(r) {
  if (r.type!=='dish') return '';
  if (!r.name.trim()) return '菜名缺失';
  if (!r.price.trim()) return '价格缺失';
  const amount=Number(r.price);
  if (Number.isFinite(amount) && (amount<1 || amount>9999)) return '价格异常';
  if (r.duplicateOf) return '疑似重复';
  if (r.status!=='verified' && ((r.confidence ?? 1)<.6 || (r.match ?? 1)<.7)) return '低置信度';
  return '';
}
function issueColor(r) { const x=issue(r); return x==='疑似重复'?'blue':x==='低置信度'||x==='价格异常'?'yellow':x?'red':''; }
function badge(r) { const x=issue(r), color=issueColor(r); return x?`<span class="pill ${color==='yellow'?'amber':color}">${x}</span>`:`<span class="pill ${r.status==='verified'?'green':'amber'}">${r.status==='verified'?'已校验':'待校验'}</span>`; }
function detectDuplicates() {
  const seen=new Map();
  for (const r of records()) {
    r.duplicateOf=null;
    if (r.type!=='dish' || !r.name.trim() || !r.price.trim()) continue;
    const key=`${r.name.trim().toLocaleLowerCase()}|${r.price.trim()}`;
    if (seen.has(key) && !r.duplicateIgnored) r.duplicateOf=seen.get(key);
    else if (!seen.has(key)) seen.set(key,r.id);
  }
}
function newRecord(data={}) { return {id:Math.max(0,...records().map(r=>r.id))+1,name:'',price:'',category:'',type:'dish',confidence:1,match:1,status:'pending',imageId:image()?.id,sourceIds:image()?[image().id]:[],duplicateIgnored:false,...data}; }
function refresh() { detectDuplicates();persist();renderHeader();renderPhotos();renderRows();renderDishes(); }
function renderHeader() {
  const b=batch();
  $('batchTitle').textContent=b.store;
  $('batchDate').textContent=b.date;
  $('batchStatus').textContent=b.done?'批次已完成':'校验进行中';
  $('batchStatus').className=`pill ${b.done?'green':'amber'}`;
  $('batchSelect').innerHTML=state.batches.map(x=>`<option value="${esc(x.id)}" ${x.id===b.id?'selected':''}>${esc(x.store)} · ${esc(x.date)}${x.mode==='sample'?'（样例）':''}</option>`).join('');
  $('photoCountLabel').textContent=`${b.images.length} 张菜单图片`;
  $('storeCount').textContent=new Set(state.batches.map(x=>x.store)).size;
}
function renderRows() {
  const current=image();
  let arr=records().filter(r=>r.imageId===current?.id && r.type!=='invalid');
  $('allNum').textContent=arr.length;
  if(filterMode==='anomaly')arr=arr.filter(r=>issue(r));
  if(filterMode==='pending')arr=arr.filter(r=>r.status!=='verified');
  if(filterMode==='verified')arr=arr.filter(r=>r.status==='verified');
  $('recordRows').innerHTML=arr.length?arr.map(r=>`<div class="record ${activeId===r.id?'selected':''} ${issueColor(r)?'anomaly-'+issueColor(r):''}" data-id="${r.id}" tabindex="0"><div class="checkmark ${r.status==='verified'?'checked':''}">${r.status==='verified'?'✓':''}</div><div><div class="record-name">${esc(r.name||'（菜名缺失）')}</div><div class="record-meta"><span>${r.type==='header'?'分类标题':esc(r.category||'未分类')}</span>${badge(r)}</div></div><div class="price">${r.price?'¥'+esc(r.price):'—'}</div></div>`).join(''):'<div class="empty">本张图片暂无记录。可粘贴 OCR 文本解析，或手动新增。</div>';
  $('recordRows').querySelectorAll('.record').forEach(el=>{el.onclick=()=>selectRecord(Number(el.dataset.id));el.ondblclick=()=>openEdit(Number(el.dataset.id));el.onkeydown=e=>{if(e.key==='Enter')openEdit(Number(el.dataset.id));};});
  const dishes=records().filter(r=>r.type==='dish'), verified=dishes.filter(r=>r.status==='verified').length, anomalies=dishes.filter(r=>issue(r)&&issue(r)!=='疑似重复').length, dupes=dishes.filter(r=>r.duplicateOf).length;
  $('verifiedCount').textContent=verified;$('totalCount').textContent=dishes.length;$('progressText').textContent=`${verified} / ${dishes.length}`;$('progressFill').style.width=`${dishes.length?verified/dishes.length*100:0}%`;
  $('anomalyCount').textContent=`${anomalies} 项待处理`;$('duplicateCount').textContent=`${dupes} 项疑似重复`;
  $('dishTotal').textContent=state.batches.reduce((n,b)=>n+b.records.filter(r=>r.type==='dish').length,0);
  $('dishPending').textContent=state.batches.reduce((n,b)=>n+b.records.filter(r=>r.type==='dish'&&r.status!=='verified').length,0);
  $('dishDupes').textContent=state.batches.reduce((n,b)=>n+b.records.filter(r=>r.type==='dish'&&r.duplicateOf).length,0);
}
function selectRecord(id) {
  activeId=id;const r=records().find(x=>x.id===id);if(!r)return;
  const i=batch().images.findIndex(x=>x.id===r.imageId);if(i>=0 && i!==currentPhoto){currentPhoto=i;renderPhotos();}
  document.querySelectorAll('.ocrbox').forEach(x=>x.classList.toggle('focus',Number(x.dataset.recordId)===id));renderRows();
}
function openDB(){return new Promise((resolve,reject)=>{const req=indexedDB.open('menu-demo-images',1);req.onupgradeneeded=()=>req.result.createObjectStore('images');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});}
async function imageStore(mode,id,value){const db=await openDB();return new Promise((resolve,reject)=>{const tx=db.transaction('images',mode),store=tx.objectStore('images'),req=mode==='readonly'?store.get(id):value===null?store.delete(id):store.put(value,id);req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);tx.oncomplete=()=>db.close();});}
function readFile(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(reader.error);reader.readAsDataURL(file);});}
let photoRenderToken=0;
async function renderPhotos() {
  const b=batch(), p=image(), token=++photoRenderToken;
  $('photoIndex').textContent=`${String(currentPhoto+1).padStart(2,'0')} / ${String(b.images.length).padStart(2,'0')}`;
  $('photoCaption').textContent=b.mode==='sample'?'样例图片 · 示意识别框':'上传图片 · 无 OCR 坐标框';
  $('ocrText').value=p?.ocrText||'';
  $('ocrText').placeholder=b.mode==='sample'?'样例已附带模拟识别记录；可在这里粘贴文本重新解析':'粘贴这张图片的 OCR 文本，每行一项。例如：热菜\n宫保鸡丁 38元\n麻婆豆腐 28元';
  $('imageStatus').textContent=p?.status==='sample'?'样例数据':p?.status==='parsed'?'文本已解析':'待录入文本';
  $('imageStatus').className=`pill ${p?.status==='parsed'?'green':'amber'}`;
  $('imageProgress').style.width=p?.status==='parsed'||p?.status==='sample'?'100%':'0%';
  const src=async pic=>{if(pic.status==='sample')return 'sample-menu.svg';if(imageCache.has(pic.id))return imageCache.get(pic.id);try{const value=await imageStore('readonly',pic.id);if(value){imageCache.set(pic.id,value);return value;}}catch{}return '';};
  const urls=await Promise.all(b.images.map(src));if(token!==photoRenderToken)return;
  $('menuImage').src=urls[currentPhoto]||'';
  $('menuImage').alt=p?.name||'菜单图片';
  $('photoInner').style.transform=`rotate(${p?.angle||0}deg) scale(${zoom})`;
  $('thumbnails').innerHTML=b.images.map((pic,i)=>`<button class="thumb ${i===currentPhoto?'active':''}" data-i="${i}" title="${esc(pic.name)}"><img src="${urls[i]||''}" alt="${esc(pic.name)}"></button>`).join('')+`<span class="thumbmore">共 ${b.images.length} 张</span>`;
  $('thumbnails').querySelectorAll('[data-i]').forEach(el=>el.onclick=()=>{currentPhoto=Number(el.dataset.i);activeId=null;renderPhotos();renderRows();});
  $('photoInner').querySelectorAll('.ocrbox').forEach(el=>el.remove());
  if(b.mode==='sample') {
    const tops=[19,32,46,60,74];
    records().filter(r=>r.imageId===p.id&&r.box).forEach(r=>{const box=document.createElement('button');box.type='button';box.className='ocrbox'+(r.id===activeId?' focus':'');box.dataset.recordId=r.id;box.style.cssText=`left:13%;top:${tops[(r.box-1)%5]}%;width:75%;height:7%;`;box.title=`${r.name} · 点击定位记录`;box.innerHTML=`<span class="box-tag">${String(r.box).padStart(2,'0')} · ${Math.round(r.confidence*100)}%</span>`;box.onclick=()=>selectRecord(r.id);$('photoInner').append(box);});
  }
}
function renderStoreOptions(){const upload=$('uploadStore'),old=upload.value||batch().store;upload.innerHTML=state.stores.map(s=>`<option value="${esc(s)}">${esc(s)}</option>`).join('');upload.value=state.stores.includes(old)?old:batch().store;const filter=$('storeFilter'),prior=filter.value||'all';filter.innerHTML='<option value="all">全部门店</option>'+state.stores.map(s=>`<option value="${esc(s)}">${esc(s)}</option>`).join('');filter.value=state.stores.includes(prior)?prior:'all';}
function filteredDishes(){const s=$('storeFilter').value,c=$('categoryFilter').value,q=$('searchDishes').value.trim().toLocaleLowerCase();return state.batches.flatMap(b=>b.records.filter(r=>r.type==='dish'&&(s==='all'||b.store===s)&&(c==='all'||r.category===c)&&(!q||r.name.toLocaleLowerCase().includes(q))).map(r=>({...r,store:b.store,date:b.date})));}
function renderDishes(){renderStoreOptions();const cat=$('categoryFilter'),old=cat.value||'all',cats=[...new Set(state.batches.flatMap(b=>b.records.filter(r=>r.type==='dish').map(r=>r.category)).filter(Boolean))];cat.innerHTML='<option value="all">全部分类</option>'+cats.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');cat.value=cats.includes(old)?old:'all';const arr=filteredDishes();$('dishTable').innerHTML=arr.length?arr.map(r=>`<tr><td><strong>${esc(r.name||'（菜名缺失）')}</strong>${r.duplicateOf?'　<span class="pill blue">疑似重复</span>':''}</td><td class="pricecell">${r.price?'¥'+esc(r.price):'—'}</td><td>${esc(r.category||'未分类')}</td><td>${esc(r.store)}</td><td>${r.confidence==null?'手工录入':Math.round(r.confidence*100)+'%'}</td><td>${badge(r)}</td></tr>`).join(''):'<tr><td colspan="6" class="empty">没有匹配的菜品</td></tr>';}
function setView(view){currentView=view;document.querySelectorAll('.view').forEach(el=>el.classList.toggle('active',el.id===`view-${view}`));document.querySelectorAll('.nav button').forEach(el=>el.classList.toggle('active',el.dataset.view===view));if(view==='dishes')renderDishes();if(view==='upload')renderStoreOptions();}
function modal(id,on){$(id).classList.toggle('show',on);}
function openEdit(id){editingId=id;const r=records().find(x=>x.id===id);if(!r)return;$('editType').value=r.type;$('editName').value=r.name;$('editPrice').value=r.price;$('editCategory').value=r.category;$('editConfidence').value=r.confidence??1;$('editTitle').textContent=r.duplicateOf?'处理疑似重复记录':'编辑菜品记录';$('duplicateActions').classList.toggle('hidden',!r.duplicateOf);modal('editModal',true);$('editName').focus();}
function parseLines(text,imageId) {
  const lines=text.split(/\r?\n/).map(x=>x.trim()).filter(Boolean),output=[];
  let nextId=Math.max(0,...records().map(r=>r.id))+1;
  const categoryWords=/^(?:招牌)?(?:凉菜|冷盘|前菜|开胃菜|热菜|炒菜|招牌菜|特色菜|汤品|汤类|羹汤|汤羹小食|主食|面食|米饭类|面条类|饮品|酒水|饮料|甜点|甜品|点心|小吃|海鲜|烧烤|火锅|套餐|拼盘)(?:系列|菜单)?$/;
  const priceOnly=/^(?:[¥￥]\s*)?(\d+(?:\.\d{1,2})?(?:\s*[-~～]\s*\d+(?:\.\d{1,2})?)?)\s*(?:元)?$/;
  const priceAtEnd=/(?:\s+|[¥￥])(?:[¥￥]\s*)?(\d+(?:\.\d{1,2})?(?:\s*[-~～]\s*\d+(?:\.\d{1,2})?)?)\s*(?:元)?$/;
  let category='';
  for(const line of lines){
    if(categoryWords.test(line)){category=line.replace(/^(招牌)/,'').replace(/(?:系列|菜单)$/,'');output.push(newRecord({id:nextId++,name:line,type:'header',category:'',price:'',confidence:null,match:1,imageId,sourceIds:[imageId],status:'verified'}));continue;}
    const only=line.match(priceOnly);
    if(only && output.length && output.at(-1).type==='dish' && !output.at(-1).price){const prev=output.at(-1);prev.price=only[1].replace(/\s+/g,'');prev.match=.65;continue;}
    if(only){output.push(newRecord({id:nextId++,name:'',price:only[1].replace(/\s+/g,''),category,confidence:null,match:.4,imageId,sourceIds:[imageId]}));continue;}
    const match=line.match(priceAtEnd),name=match?line.slice(0,match.index).trim():line;
    output.push(newRecord({id:nextId++,name,price:match?match[1].replace(/\s+/g,''):'',category,confidence:null,match:match?1:.5,imageId,sourceIds:[imageId]}));
  }
  return output;
}
function parseCurrentText(){const p=image(),text=$('ocrText').value.trim();if(!text){toast('请先粘贴 OCR 文本');return;}if(records().some(r=>r.imageId===p.id)&&!confirm('重新解析会替换这张图片的现有记录，确定继续吗？'))return;batch().records=records().filter(r=>r.imageId!==p.id);const parsed=parseLines(text,p.id);batch().records.push(...parsed);p.ocrText=text;p.status='parsed';batch().done=false;activeId=null;refresh();toast(`已解析 ${parsed.filter(r=>r.type==='dish').length} 条菜品候选，请逐条校验`);}
function saveEdit(){const r=records().find(x=>x.id===editingId);if(!r)return;r.type=$('editType').value;r.name=$('editName').value.trim();r.price=$('editPrice').value.trim();r.category=$('editCategory').value.trim();r.confidence=Number($('editConfidence').value);r.status='verified';r.duplicateIgnored=false;batch().done=false;modal('editModal',false);refresh();toast('记录已保存并标记为已校验');}
function mergeDuplicate(){const r=records().find(x=>x.id===editingId),main=records().find(x=>x.id===r?.duplicateOf);if(!main){toast('未找到主记录');return;}main.sourceIds=[...new Set([...(main.sourceIds||[main.imageId]),...(r.sourceIds||[r.imageId])])];batch().records=records().filter(x=>x.id!==r.id);modal('editModal',false);refresh();toast('已合并，来源图片引用已保留');}
function exportXlsx(arr){arr=arr.filter(r=>r.type==='dish'&&r.name.trim());if(!arr.length){toast('没有可导出的菜品');return;}const rows=[['菜品名称','价格','分类','门店名称','批次日期'],...arr.map(r=>[r.name,r.price,r.category,r.store,r.date])],cols='ABCDE';const sheet=`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${rows.map((row,ri)=>`<row r="${ri+1}">${row.map((v,ci)=>`<c r="${cols[ci]}${ri+1}" t="inlineStr"><is><t>${xmlEsc(v)}</t></is></c>`).join('')}</row>`).join('')}</sheetData><autoFilter ref="A1:E${rows.length}"/></worksheet>`;
  const files={'[Content_Types].xml':'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>','_rels/.rels':'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>','xl/workbook.xml':'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="菜单菜品" sheetId="1" r:id="rId1"/></sheets></workbook>','xl/_rels/workbook.xml.rels':'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>','xl/worksheets/sheet1.xml':sheet};
  downloadZip(files,`菜单菜品_${today()}.xlsx`);toast(`已导出 ${arr.length} 条菜品记录`);}
function downloadZip(files,name){const enc=new TextEncoder(),entries=Object.entries(files).map(([filename,body])=>({name:enc.encode(filename),data:enc.encode(body)}));const table=Array.from({length:256},(_,n)=>{let c=n;for(let i=0;i<8;i++)c=c&1?0xedb88320^(c>>>1):c>>>1;return c>>>0;});const crc=data=>{let c=0xffffffff;for(const b of data)c=table[(c^b)&255]^(c>>>8);return(c^0xffffffff)>>>0;};const u16=n=>[n&255,(n>>>8)&255],u32=n=>[n&255,(n>>>8)&255,(n>>>16)&255,(n>>>24)&255],parts=[],central=[];let offset=0;for(const e of entries){const c=crc(e.data),local=new Uint8Array([0x50,0x4b,3,4,...u16(20),0,0,0,0,0,0,0,0,...u32(c),...u32(e.data.length),...u32(e.data.length),...u16(e.name.length),0,0]);parts.push(local,e.name,e.data);central.push(new Uint8Array([0x50,0x4b,1,2,...u16(20),...u16(20),0,0,0,0,0,0,0,0,...u32(c),...u32(e.data.length),...u32(e.data.length),...u16(e.name.length),0,0,0,0,0,0,0,0,0,0,0,0,...u32(offset),...e.name]));offset+=local.length+e.name.length+e.data.length;}const centralSize=central.reduce((n,x)=>n+x.length,0);parts.push(...central,new Uint8Array([0x50,0x4b,5,6,0,0,0,0,...u16(entries.length),...u16(entries.length),...u32(centralSize),...u32(offset),0,0]));const url=URL.createObjectURL(new Blob(parts,{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),3000);}
function chooseFiles(list){const files=Array.from(list);selectedFiles=files.filter(f=>['image/jpeg','image/png'].includes(f.type)).slice(0,30);$('selectedFiles').textContent=selectedFiles.length?selectedFiles.map(f=>f.name).join('、'):'请选择 JPG 或 PNG 图片';if(files.length>30)toast('单批最多 30 张，已保留前 30 张');}
async function startUpload(){if(!selectedFiles.length){toast('请先选择菜单图片');return;}const store=$('uploadStore').value;if(!store){toast('请先选择门店');return;}const btn=$('startOcr');btn.disabled=true;btn.textContent='正在保存图片…';$('uploadProgress').classList.remove('hidden');const b={id:uid(),store,date:today(),mode:'manual',done:false,images:[],records:[]};let failed=0;for(let i=0;i<selectedFiles.length;i++){const file=selectedFiles[i],id=uid();try{const data=await readFile(file);imageCache.set(id,data);try{await imageStore('readwrite',id,data);}catch{failed++;}b.images.push({id,name:file.name,status:'needs_text',angle:0,ocrText:''});}catch{failed++;}$('ocrFill').style.width=`${(i+1)/selectedFiles.length*100}%`;$('ocrPercent').textContent=`${Math.round((i+1)/selectedFiles.length*100)}%`;$('ocrMessage').textContent=`已载入 ${i+1} / ${selectedFiles.length} 张图片`;}
  btn.disabled=false;btn.textContent='创建批次并上传 →';$('uploadProgress').classList.add('hidden');selectedFiles=[];$('fileInput').value='';$('selectedFiles').textContent='还没有选择图片';if(!b.images.length){toast('图片读取失败，请重试');return;}state.batches.unshift(b);state.activeBatchId=b.id;currentPhoto=0;activeId=null;zoom=1;refresh();setView('verify');toast(`已创建批次：${b.images.length} 张图片。请粘贴 OCR 文本或手动新增记录${failed?'；部分图片仅本次可见':''}`);}
function switchBatch(id){if(!state.batches.some(b=>b.id===id))return;state.activeBatchId=id;currentPhoto=0;activeId=null;zoom=1;refresh();}
async function deletePhoto(){const p=image();if(!p||!confirm(`删除“${p.name}”及其关联记录？`))return;batch().images.splice(currentPhoto,1);batch().records=records().filter(r=>{r.sourceIds=(r.sourceIds||[r.imageId]).filter(id=>id!==p.id);if(r.imageId===p.id&&r.sourceIds.length)r.imageId=r.sourceIds[0];return r.imageId!==p.id;});batch().done=false;if(p.status!=='sample'){imageCache.delete(p.id);try{await imageStore('readwrite',p.id,null);}catch{}}if(!batch().images.length){state.batches=state.batches.filter(b=>b.id!==batch().id);if(!state.batches.length)state.batches.push(sampleBatch());state.activeBatchId=state.batches[0].id;}currentPhoto=Math.max(0,Math.min(currentPhoto,batch().images.length-1));refresh();toast('图片已删除');}
function bind(){
  document.querySelectorAll('.nav button').forEach(x=>x.onclick=()=>setView(x.dataset.view));$('uploadOpen').onclick=()=>setView('upload');$('saveBtn').onclick=()=>{persist();toast('进度已保存到本机浏览器');};$('batchSelect').onchange=e=>switchBatch(e.target.value);
  document.querySelectorAll('.filter').forEach(x=>x.onclick=()=>{filterMode=x.dataset.filter;document.querySelectorAll('.filter').forEach(y=>y.classList.toggle('on',y===x));renderRows();});
  $('addRecord').onclick=()=>{const r=newRecord({category:records().findLast(x=>x.imageId===image().id&&x.category)?.category||''});records().push(r);batch().done=false;refresh();openEdit(r.id);};
  $('saveEdit').onclick=saveEdit;$('cancelEdit').onclick=()=>modal('editModal',false);document.querySelector('.closeModal').onclick=()=>modal('editModal',false);$('deleteRecord').onclick=()=>{batch().records=records().filter(r=>r.id!==editingId);batch().done=false;modal('editModal',false);refresh();toast('记录已删除');};
  $('mergeDupe').onclick=mergeDuplicate;$('markUnique').onclick=()=>{const r=records().find(x=>x.id===editingId);r.duplicateIgnored=true;r.status='verified';modal('editModal',false);refresh();toast('已标记为非重复');};
  $('dedupeBtn').onclick=()=>{detectDuplicates();refresh();toast(`发现 ${records().filter(r=>r.duplicateOf).length} 条疑似重复记录`);};
  $('finishBtn').onclick=()=>{const dishes=records().filter(r=>r.type==='dish');if(!dishes.length){toast('请先解析文本或新增菜品记录');return;}const problems=dishes.filter(r=>r.status!=='verified'||issue(r));if(problems.length){toast(`还有 ${problems.length} 条菜品待校验或处理异常`);filterMode=problems.some(r=>issue(r))?'anomaly':'pending';document.querySelectorAll('.filter').forEach(x=>x.classList.toggle('on',x.dataset.filter===filterMode));renderRows();return;}batch().done=true;refresh();toast('批次校验完成，可以导出 Excel');};
  $('rotateBtn').onclick=()=>{image().angle=(image().angle+90)%360;refresh();toast('图片已旋转 90°');};$('zoomIn').onclick=()=>{zoom=Math.min(1.6,zoom+.1);renderPhotos();};$('zoomOut').onclick=()=>{zoom=Math.max(.6,zoom-.1);renderPhotos();};$('resetZoom').onclick=()=>{zoom=1;image().angle=0;refresh();};$('deletePhoto').onclick=deletePhoto;
  $('retryOcr').onclick=()=>{if(!image().ocrText){toast('当前图片没有 OCR 文本，请先粘贴文本');return;}parseCurrentText();};$('parseTextBtn').onclick=parseCurrentText;
  $('exportTop').onclick=()=>exportXlsx(records().map(r=>({...r,store:batch().store,date:batch().date})));$('exportAll').onclick=()=>exportXlsx(state.batches.flatMap(b=>b.records.map(r=>({...r,store:b.store,date:b.date}))));$('exportFiltered').onclick=()=>exportXlsx(filteredDishes());
  $('storeFilter').onchange=renderDishes;$('categoryFilter').onchange=renderDishes;$('searchDishes').oninput=renderDishes;
  $('uploadBox').onclick=e=>{if(e.target!==$('fileInput'))$('fileInput').click();};$('fileInput').onchange=e=>chooseFiles(e.target.files);$('uploadBox').ondragover=e=>{e.preventDefault();$('uploadBox').classList.add('drag');};$('uploadBox').ondragleave=()=>$('uploadBox').classList.remove('drag');$('uploadBox').ondrop=e=>{e.preventDefault();$('uploadBox').classList.remove('drag');chooseFiles(e.dataTransfer.files);};$('startOcr').onclick=startUpload;
  $('addStoreInline').onclick=()=>{modal('storeModal',true);$('newStoreName').value='';$('newStoreName').focus();};document.querySelectorAll('.closeStore').forEach(x=>x.onclick=()=>modal('storeModal',false));$('saveStore').onclick=()=>{const name=$('newStoreName').value.trim();if(!name){toast('请填写门店名称');return;}if(!state.stores.includes(name))state.stores.push(name);persist();renderStoreOptions();$('uploadStore').value=name;modal('storeModal',false);toast('门店已添加');};
  $('sampleBtn').onclick=()=>{state.batches=state.batches.filter(b=>b.id!=='sample');state.batches.push(sampleBatch());switchBatch('sample');setView('verify');toast('演示样例已重置');};
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){modal('editModal',false);modal('storeModal',false);}if(e.key==='Enter'&&$('storeModal').classList.contains('show'))$('saveStore').click();});
}
bind();refresh();
