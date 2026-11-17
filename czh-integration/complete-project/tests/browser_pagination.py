"""Browser regression against a real backend with more than one result page."""
import os
import sys
import tempfile
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / 'backend'))
import db
from server import create_server

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
    os.environ['MENU_DB_PATH'] = str(Path(temporary) / 'menu.db')
    db.init_db()
    store = db.get_or_create_store('分页验收门店')
    now = db.now_iso()
    with db.connect() as connection:
        connection.executemany(
            'INSERT INTO dish_records(store_id, dish_name, created_at, updated_at) VALUES (?, ?, ?, ?)',
            ((store['id'], f'分页验收菜品{i}', now, now) for i in range(2001)),
        )
    server = create_server('127.0.0.1', 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=os.environ.get('MENU_BROWSER_PATH') or None, headless=True)
            page = browser.new_page()
            page.goto(f'http://127.0.0.1:{server.server_address[1]}/', wait_until='domcontentloaded')
            page.get_by_text('后端已连接').wait_for(timeout=30000)
            assert '共 2001 条' in page.locator('#count').inner_text()
            page.locator('#search').fill('分页验收菜品0')
            page.get_by_text('分页验收菜品0', exact=True).wait_for()
            page.reload(wait_until='domcontentloaded')
            page.get_by_text('后端已连接').wait_for(timeout=30000)
            assert '共 2001 条' in page.locator('#count').inner_text()
            browser.close()
            print('PASS: browser loads, searches and reloads all 2001 real stored records')
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
