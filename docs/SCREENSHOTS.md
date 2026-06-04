# 截图刷新说明

README 中的产品截图保存在 `artifacts/screenshots/`：

- `home.png`：首页交付就绪度。
- `demo.png`：交付演示台。
- `run-detail.png`：一键完整闭环后的结果页。

刷新前先启动本地服务：

```powershell
uvicorn app.main:app --reload
```

然后运行：

```powershell
@'
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path("artifacts/screenshots")
out.mkdir(parents=True, exist_ok=True)
edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
base = "http://127.0.0.1:8000"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=edge)
    page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
    page.goto(base + "/", wait_until="networkidle")
    page.screenshot(path=str(out / "home.png"), full_page=True)
    page.goto(base + "/demo", wait_until="networkidle")
    page.screenshot(path=str(out / "demo.png"), full_page=True)
    page.locator('form[action="/demo/complete"] button').click()
    page.wait_for_load_state("networkidle")
    assert "6/6 已确认" in page.inner_text("body")
    assert "已签收" in page.inner_text("body")
    page.screenshot(path=str(out / "run-detail.png"), full_page=True)
    browser.close()
'@ | py -
```

截图刷新后建议再执行：

```powershell
py -B -m pytest -q -p no:cacheprovider
.\scripts\smoke_check.ps1 -BaseUrl http://127.0.0.1:8000 -CompleteDemo
```
