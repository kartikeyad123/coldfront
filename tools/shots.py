"""Take screenshots of every view of the running app (http://localhost:8765)."""
import sys, time
from playwright.sync_api import sync_playwright
out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/shots"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1440, "height": int(sys.argv[2]) if len(sys.argv) > 2 else 900}, device_scale_factor=1)
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto("http://localhost:8765"); pg.wait_for_timeout(9000)
    def shot(name, full=True):
        pg.wait_for_timeout(3500)
        ex = pg.locator("div[data-testid='stException']")
        if ex.count(): print("EXCEPTION on", name, ex.first.inner_text()[:600])
        pg.screenshot(path=f"{out}/{name}.png", full_page=full)
    def nav(v):
        pg.get_by_role("radio", name=v, exact=True).click() if pg.get_by_role("radio", name=v, exact=True).count() else pg.get_by_text(v, exact=True).first.click()
    shot("home")
    pg.get_by_role("button", name="Start first shift").click(); shot("wo1_brief")
    pg.get_by_role("button", name="Start mission").click(); shot("wo1_debrief")
    pg.get_by_role("button", name="All missions").click(); shot("wo_list")
    pg.get_by_role("button", name="Open").nth(2).click(); shot("wo3_brief")
    pg.get_by_role("button", name="Start mission").click(); shot("wo3_pause")
    pg.get_by_role("button", name="Resume mission").click(); shot("wo3_debrief")
    for v in ("Console", "Chiller lab", "Compare", "Proof"):
        nav(v); pg.wait_for_timeout(4000 if v != "Proof" else 15000); shot(v.lower().replace(" ", "_"))
    print("console errors:", errs[:5])
    b.close()
