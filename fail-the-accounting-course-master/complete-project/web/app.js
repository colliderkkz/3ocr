'use strict';
const $ = id => document.getElementById(id);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let dishes = [], stores = [], busy = false, previewAngle=0, previewScale=1, refreshVersion=0;
function notice(message, error=false) { const el=$('notice'); el.textContent=message; el.classList.toggle('error',error); el.hidden=false; }
async function request(path, options={}) {
  let response;
  try { response=await fetch(path, options); } catch { throw new Error('无法连接服务，请确认应用正在运行'); }
  let data;
  try { data=await response.json(); } catch { throw new Error(`服务响应异常（HTTP ${response.status}）`); }
  if(!response.ok) throw new Error(data.error || `请求失败（HTTP ${response.status}）`);
  return data;
}
function renderStores() {
  const old=$('store-filter').value;
  $('stores').innerHTML=stores.map(s=>`<option value="${escapeHtml(s.name)}"></option>`).join('');
  $('store-filter').innerHTML='<option value="">全部门店</option>'+stores.map(s=>`<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('');
  if(stores.some(s=>String(s.id)===old)) $('store-filter').value=old;
}
function render() {
  const store=$('store-filter').value, q=$('search').value.trim().toLocaleLowerCase();
  const visible=dishes.filter(d=>(!store || String(d.store_id)===store) && (!q || d.dish_name.toLocaleLowerCase().includes(q)));
  const counts=new Map(); for(const d of dishes){const key=`${d.store_id}|${d.dish_name.trim()}|${d.price.trim()}`;if(d.dish_name.trim()&&d.price.trim())counts.set(key,(counts.get(key)||0)+1);}
  $('records').innerHTML=visible.length ? visible.map(d=>`<tr data-id="${d.id}"><td><strong>${escapeHtml(d.dish_name)}</strong>${counts.get(`${d.store_id}|${d.dish_name.trim()}|${d.price.trim()}`)>1?' <span class="pill">疑似重复</span>':''}</td><td>${escapeHtml(d.price || '—')}</td><td>${escapeHtml(d.category || '未分类')}</td><td>${escapeHtml(d.store_name)}</td><td><span class="pill ${d.verify_status==='verified'?'done':''}">${d.verify_status==='verified'?'已校验':'待校验'}</span></td><td class="actions"><button class="link-button" data-action="edit" type="button">编辑</button>${d.image_id&&d.has_image?'<button class="link-button" data-action="image" type="button">原图</button>':''}${counts.get(`${d.store_id}|${d.dish_name.trim()}|${d.price.trim()}`)>1?'<button class="link-button" data-action="merge" type="button">合并重复</button>':''}<button class="link-button danger" data-action="delete" type="button">删除</button></td></tr>`).join('') : '<tr><td colspan="6" class="empty">暂无匹配菜品。上传菜单后，识别结果会显示在这里。</td></tr>';
  $('count').textContent=`显示 ${visible.length} 条 / 共 ${dishes.length} 条`;
}
async function refresh() {
  const version=++refreshVersion;
  try {
    const [health,storeData,firstPage]=await Promise.all([request('/api/health'),request('/api/stores'),request('/api/dishes?limit=2000')]);
    if(health.status!=='ok') throw new Error('后端状态异常');
    const allDishes=[...firstPage.dishes]; let page=firstPage;
    while(allDishes.length<page.total && page.dishes.length) {
      page=await request(`/api/dishes?limit=2000&offset=${allDishes.length}`);
      allDishes.push(...page.dishes);
    }
    if(version!==refreshVersion) return false;
    stores=storeData.stores; dishes=allDishes; renderStores(); render();
    $('connection').textContent='后端已连接'; return true;
  } catch(error) { if(version===refreshVersion){$('connection').textContent='后端连接失败'; notice(error.message,true);} return false; }
}
function setBusy(value){busy=value;$('upload-button').disabled=value;$('upload-button').textContent=value?'正在识别，请稍候…':'开始识别';}
$('upload-form').addEventListener('submit',async event=>{
  event.preventDefault(); if(busy)return;
  const file=$('image').files[0], store=$('store').value.trim();
  if(!store || !file){notice('请填写门店并选择图片',true);return;}
  if(file.size>30*1024*1024){notice('图片超过 30 MB，请选择较小的文件',true);return;}
  const form=new FormData();form.append('store_name',store);form.append('image',file,file.name);
  setBusy(true); notice('正在上传并识别图片，请稍候…');
  try {
    const result=await request('/api/ocr/recognize',{method:'POST',body:form});
    const loaded=await refresh();
    if(!loaded){notice('识别已完成并保存，但重新加载失败；请点击刷新数据',true);return;}
    $('store-filter').value=String(result.store.id); $('search').value=''; render();
    $('image').value=''; notice(`识别完成，已保存 ${result.records.filter(r=>r.record_type==='dish').length} 条菜品。请核对后编辑。`);
  } catch(error){notice(`识别失败：${error.message}`,true);} finally{setBusy(false);}
});
$('records').addEventListener('click',async event=>{
  const button=event.target.closest('button[data-action]'); if(!button)return;
  const row=button.closest('tr'), dish=dishes.find(d=>d.id===Number(row.dataset.id)); if(!dish)return;
  if(button.dataset.action==='edit'){
    $('edit-title').textContent='校验菜品'; $('edit-store-wrap').hidden=true;
    $('edit-id').value=dish.id; $('edit-name').value=dish.dish_name; $('edit-price').value=dish.price; $('edit-category').value=dish.category;
    $('edit-error').hidden=true; $('edit-dialog').showModal(); $('edit-name').focus();
  } else if(button.dataset.action==='image') {
    previewAngle=0;previewScale=1;updatePreview();$('preview').src=`/api/images/${encodeURIComponent(dish.image_id)}/file`; $('preview-section').hidden=false; $('preview-section').scrollIntoView({behavior:'smooth'});
  } else if((button.dataset.action==='delete'||button.dataset.action==='merge') && confirm(button.dataset.action==='merge'?`合并将删除当前“${dish.dish_name}”记录，保留另一条同门店、同名同价记录；当前记录的图片关联不会转移。确定继续吗？`:`确定删除“${dish.dish_name}”吗？`)) {
    button.disabled=true;
    try { await request(`/api/dishes/${dish.id}`,{method:'DELETE'}); const loaded=await refresh(); notice(loaded?(button.dataset.action==='merge'?'重复记录已合并':'菜品已从服务器删除'):'操作已保存，但重新加载失败；请点击刷新数据',!loaded); }
    catch(error){notice(`删除失败：${error.message}`,true);button.disabled=false;}
  }
});
$('edit-form').addEventListener('submit',async event=>{
  event.preventDefault();const button=$('save-edit'), name=$('edit-name').value.trim();
  if(!name){$('edit-error').textContent='请填写菜品名称';$('edit-error').hidden=false;return;}
  button.disabled=true; $('edit-error').hidden=true;
  try {
    const id=$('edit-id').value, payload={dish_name:name,price:$('edit-price').value.trim(),category:$('edit-category').value.trim(),verify_status:'verified',anomaly:'none'};
    if(!id){if(!$('edit-store').value)throw new Error('请先选择门店');payload.store_id=Number($('edit-store').value);}
    await request(id?`/api/dishes/${encodeURIComponent(id)}`:'/api/dishes',{method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    $('edit-dialog').close(); const loaded=await refresh(); notice(loaded?'菜品已保存到服务器':'菜品已保存，但重新加载失败；请点击刷新数据',!loaded);
  } catch(error) { $('edit-error').textContent=`保存失败：${error.message}`; $('edit-error').hidden=false; }
  finally{button.disabled=false;}
});
$('cancel-edit').onclick=()=>$('edit-dialog').close(); $('close-edit').onclick=()=>$('edit-dialog').close(); $('close-preview').onclick=()=>{$('preview-section').hidden=true;};
function updatePreview(){$('preview').style.transform=`rotate(${previewAngle}deg) scale(${previewScale})`;}
$('preview-rotate').onclick=()=>{previewAngle=(previewAngle+90)%360;updatePreview();};$('preview-zoom-in').onclick=()=>{previewScale=Math.min(2,previewScale+.2);updatePreview();};$('preview-zoom-out').onclick=()=>{previewScale=Math.max(.4,previewScale-.2);updatePreview();};
$('parse-text').onclick=async()=>{const store=$('store').value.trim(),text=$('ocr-text').value.trim();if(!store||!text){notice('请填写门店名称和菜单文本',true);return;}const button=$('parse-text');button.disabled=true;try{const result=await request('/api/ocr/results',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_name:store,ocr_text:text})});if(!(await refresh())){notice('文本已解析并保存，但重新加载失败；请点击刷新数据',true);return;}$('store-filter').value=String(result.store.id);$('search').value='';render();$('ocr-text').value='';notice('文本已解析并保存到服务器');}catch(error){notice(`文本解析失败：${error.message}`,true);}finally{button.disabled=false;}};
$('add-dish').onclick=()=>{if(!stores.length){notice('请先上传菜单创建门店，再新增菜品',true);return;}$('edit-title').textContent='新增菜品';$('edit-id').value='';$('edit-name').value='';$('edit-price').value='';$('edit-category').value='';$('edit-store').innerHTML=stores.map(s=>`<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('');$('edit-store-wrap').hidden=false;$('edit-error').hidden=true;$('edit-dialog').showModal();$('edit-name').focus();};
$('reload').onclick=async()=>{if(await refresh())notice('数据已从服务器刷新');}; $('store-filter').onchange=render; $('search').oninput=render;
refresh();
