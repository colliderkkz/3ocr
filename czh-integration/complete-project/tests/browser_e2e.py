from pathlib import Path
import json, sys, urllib.request, zipfile, os
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parent.parent; evidence=Path(os.environ.get('MENU_EVIDENCE_DIR', root.parent/'reports'/'evidence')); evidence.mkdir(parents=True, exist_ok=True); base='http://127.0.0.1:'+os.environ.get('MENU_TEST_PORT','28435'); sample=root/'ocr'/'sample'/'sample-menu.png'; logs=[]
def log(x): logs.append(x); print(x,flush=True)
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=os.environ.get('MENU_BROWSER_PATH') or None,headless=True)
  context=browser.new_context(viewport={'width':1440,'height':900},accept_downloads=True); page=context.new_page(); errors=[]
  page.on('pageerror',lambda e: errors.append(str(e)))
  page.goto(base+'/',wait_until='networkidle'); page.get_by_text('后端已连接').wait_for()
  log('PASS 启动：统一入口，页面连接真实后端')
  page.locator('#store').fill('端到端测试门店'); page.locator('#ocr-text').fill('番茄炒蛋 25元'); page.locator('#parse-text').click(); page.get_by_text('文本已解析并保存到服务器').wait_for(); page.reload(wait_until='domcontentloaded'); page.get_by_text('后端已连接').wait_for(); page.get_by_text('番茄炒蛋',exact=True).wait_for(); assert page.locator('tr').filter(has_text='番茄炒蛋').get_by_role('button',name='原图').count()==0
  log('PASS 外部文本：后端解析、保存并在刷新后读取，无假原图')
  page.locator('#store').fill('端到端测试门店'); page.locator('#image').set_input_files(str(sample))
  with page.expect_response(lambda r:'/api/ocr/recognize' in r.url and r.request.method=='POST',timeout=90000) as pending: page.locator('#upload-button').click()
  response=pending.value; data=response.json(); assert response.status==201, data
  page.get_by_text('识别完成，已保存',exact=False).wait_for(timeout=15000)
  dishes=[x for x in data['records'] if x['record_type']=='dish']; assert len(dishes)>=3
  log('PASS 上传/OCR：真实服务返回 '+str(len(dishes))+' 条菜品')
  row=page.locator('tr[data-id]').filter(has_text='宫保鸡丁').first; row.wait_for(); row.get_by_role('button',name='编辑').click()
  page.locator('#edit-name').fill('宫保鸡丁验收'); page.locator('#edit-price').fill('42')
  with page.expect_response(lambda r:'/api/dishes/' in r.url and r.request.method=='PUT') as pending: page.locator('#save-edit').click()
  assert pending.value.status==200; page.get_by_text('菜品已保存到服务器').wait_for(); log('PASS 编辑保存：PUT 返回 200')
  page.reload(wait_until='domcontentloaded'); page.get_by_text('后端已连接').wait_for(); page.get_by_text('宫保鸡丁验收',exact=True).wait_for(); assert page.locator('tr').filter(has_text='宫保鸡丁验收').get_by_text('42',exact=True).count()
  with urllib.request.urlopen(base+'/api/dishes?limit=2000') as resp: rows=json.load(resp)['dishes']
  saved=next(r for r in rows if r['dish_name']=='宫保鸡丁验收'); assert saved['price']=='42' and saved['verify_status']=='verified'
  log('PASS 保存/刷新：数据库查询和页面刷新均保留菜名与价格')
  page.locator('tr').filter(has_text='宫保鸡丁验收').get_by_role('button',name='原图').click(); page.locator('#preview').wait_for(state='visible')
  assert page.locator('#preview').evaluate('(img) => img.complete && img.naturalWidth > 0')
  page.locator('#preview-rotate').click();page.locator('#preview-zoom-in').click();assert '90deg' in page.locator('#preview').get_attribute('style')
  page.screenshot(path=str(evidence/'formal-e2e-saved.png'),full_page=True); log('PASS 原图：服务端图片可读取，已保存真实截图')
  with page.expect_download() as d: page.locator('#export').click()
  download=d.value; dest=evidence/'formal-export-test.xlsx'; download.save_as(str(dest))
  with zipfile.ZipFile(dest) as z: sheet=z.read('xl/worksheets/sheet1.xml').decode('utf-8')
  assert '宫保鸡丁验收' in sheet and '42' in sheet; log('PASS 导出：实际下载 XLSX 内容包含编辑后的菜名及价格')
  page.on('dialog',lambda dialog: dialog.accept())
  row=page.locator('tr').filter(has_text='宫保鸡丁验收');
  with page.expect_response(lambda r:'/api/dishes/' in r.url and r.request.method=='DELETE') as pending: row.get_by_role('button',name='删除').click()
  assert pending.value.status==200; page.get_by_text('菜品已从服务器删除').wait_for(); page.reload(wait_until='domcontentloaded'); page.get_by_text('后端已连接').wait_for(); assert page.get_by_text('宫保鸡丁验收',exact=True).count()==0
  with urllib.request.urlopen(base+'/api/dishes?limit=2000') as resp: rows=json.load(resp)['dishes']
  assert not any(r['dish_name']=='宫保鸡丁验收' for r in rows); log('PASS 删除：API、刷新和数据库查询均确认删除')
  page.locator('#store').fill('端到端测试门店'); page.locator('#image').set_input_files({'name':'fake.png','mimeType':'image/png','buffer':b'not an image'*30})
  with page.expect_response(lambda r:'/api/ocr/recognize' in r.url and r.request.method=='POST') as pending: page.locator('#upload-button').click()
  assert pending.value.status==415; page.get_by_text('识别失败',exact=False).wait_for(); log('PASS 异常：伪造 PNG 返回 415 并显示失败提示')
  page.locator('#add-dish').click(); page.locator('#edit-name').fill('手工菜品'); page.locator('#edit-price').fill('18'); page.locator('#save-edit').click(); page.get_by_text('菜品已保存到服务器').wait_for(); page.reload(wait_until='domcontentloaded'); page.get_by_text('后端已连接').wait_for(); page.get_by_text('手工菜品',exact=True).wait_for(); log('PASS 手工新增：服务器保存后刷新仍可读取')
  page.locator('#add-dish').click(); page.locator('#edit-name').fill('手工菜品'); page.locator('#edit-price').fill('18'); page.locator('#save-edit').click(); page.get_by_text('疑似重复').first.wait_for(); page.locator('tr').filter(has_text='手工菜品').first.get_by_role('button',name='合并重复').click(); page.get_by_text('重复记录已合并').wait_for(); assert page.locator('tr').filter(has_text='手工菜品').count()==1; log('PASS 重复合并：服务器删除当前重复记录并保留另一条')
  page.locator('#store').fill('端到端测试门店'); page.locator('#image').set_input_files(str(sample))
  page.route('**/api/ocr/recognize', lambda route: route.fulfill(status=422, content_type='application/json', body=json.dumps({'error':'模拟识别引擎故障'},ensure_ascii=False)))
  page.locator('#upload-button').click(); page.get_by_text('模拟识别引擎故障',exact=False).wait_for(); page.unroute('**/api/ocr/recognize'); log('PASS OCR 故障提示：模拟服务 422，页面明确显示失败')
  row=page.locator('tr[data-id]').first; row.get_by_role('button',name='编辑').click(); page.locator('#edit-name').fill('不能保存的修改')
  page.route('**/api/dishes/*', lambda route: route.fulfill(status=500, content_type='application/json', body=json.dumps({'error':'模拟保存故障'},ensure_ascii=False)))
  page.locator('#save-edit').click(); page.get_by_text('保存失败：模拟保存故障',exact=False).wait_for(); assert page.locator('#edit-dialog').is_visible(); page.unroute('**/api/dishes/*'); page.locator('#cancel-edit').click(); page.reload(wait_until='domcontentloaded'); page.get_by_text('后端已连接').wait_for(); assert page.get_by_text('不能保存的修改',exact=True).count()==0
  log('PASS 保存故障提示：模拟服务 500，保留编辑框且刷新后没有假保存')
  row=page.locator('tr[data-id]').first; row.get_by_role('button',name='编辑').click(); page.locator('#edit-name').fill('保存后刷新失败')
  page.route('**/api/dishes?limit=2000', lambda route: route.fulfill(status=500, content_type='application/json', body='{"error":"模拟刷新故障"}'))
  page.locator('#save-edit').click(); page.get_by_text('菜品已保存，但重新加载失败',exact=False).wait_for(); page.unroute('**/api/dishes?limit=2000')
  page.reload(wait_until='domcontentloaded'); page.get_by_text('后端已连接').wait_for(); page.get_by_text('保存后刷新失败',exact=True).wait_for()
  log('PASS 保存后刷新失败：模拟读取 500，提示已保存；恢复后从真实数据库读取')
  assert not errors,errors; log('PASS 运行时：未捕获浏览器页面异常')
  browser.close()
except Exception as e:
 log('FAIL '+repr(e)); raise
finally:
 (evidence/'formal-e2e.log').write_text('\n'.join(logs)+'\n',encoding='utf-8')
