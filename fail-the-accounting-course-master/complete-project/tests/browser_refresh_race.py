"""Exercise competing refreshes with a real backend and a delayed HTTP response."""
import os, sys, tempfile, threading
from pathlib import Path
from playwright.sync_api import sync_playwright
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / 'backend'))
import db
from server import create_server
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
    os.environ['MENU_DB_PATH'] = str(Path(temporary) / 'menu.db')
    db.init_db()
    store = db.get_or_create_store('刷新测试')
    server = create_server('127.0.0.1', 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ.get('MENU_BROWSER_PATH') or None, headless=True)
            page = browser.new_page()
            page.goto(f'http://127.0.0.1:{server.server_address[1]}', wait_until='networkidle')
            page.get_by_text('后端已连接').wait_for()
            page.evaluate('''async (storeId) => {
                const original=window.fetch; let release, captured;
                const gate=new Promise(resolve=>release=resolve);
                const ready=new Promise(resolve=>captured=resolve);
                let first=true;
                window.fetch=async (...args)=>{
                    const response=await original(...args);
                    if(first && String(args[0]).startsWith('/api/dishes?')){first=false;captured();await gate;}
                    return response;
                };
                const older=refresh(); await ready;
                const saved=await original('/api/dishes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:storeId,dish_name:'较新菜品'})});
                if(!saved.ok) throw new Error('test setup failed');
                await refresh(); release(); await older; window.fetch=original;
            }''', store['id'])
            page.get_by_text('较新菜品', exact=True).wait_for()
            browser.close()
            print('PASS: delayed older refresh does not overwrite newer real server data')
    finally:
        server.shutdown(); server.server_close(); worker.join(timeout=5)
