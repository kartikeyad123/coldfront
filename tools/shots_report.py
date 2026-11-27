"""Screenshots used in the report and slides (app must be running on :8765)."""
import sys
from playwright.sync_api import sync_playwright
out = "report/fig"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1440, "height": 1700}, device_scale_factor=1.5)
    pg.goto("http://localhost:8765"); pg.wait_for_timeout(9000)
    def shot(name, h=None, y=0):
        pg.wait_for_timeout(4000)
        pg.screenshot(path=f"{out}/{name}.png", clip=dict(x=110, y=y, width=1220, height=h or 1700))
    shot("UI_home", 720)
    pg.get_by_role("button", name="Start first shift").click(); shot("UI_wo1_brief", 620)
    pg.get_by_role("button", name="Start mission").click(); shot("UI_wo1_debrief", 1500)
    pg.get_by_role("button", name="All missions").click(); shot("UI_wo_list", 640)
    pg.get_by_role("button", name="Open").nth(2).click(); pg.wait_for_timeout(2500)
    pg.get_by_role("button", name="Start mission").click(); shot("UI_wo3_pause", 1380)
    pg.get_by_role("button", name="Chilled water").click(); pg.wait_for_timeout(1200)
    th = pg.get_by_role("slider").first; th.focus()
    for _ in range(14): pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(120)
    pg.wait_for_timeout(1500); pg.keyboard.press("Escape"); pg.wait_for_timeout(800)
    pg.get_by_role("button", name="Resume mission").click(); shot("UI_wo3_debrief", 1500)
    pg.get_by_role("radio", name="Console", exact=True).click(); pg.wait_for_timeout(5000); shot("UI_console", 1500)
    pg.get_by_role("radio", name="Chiller lab", exact=True).click(); pg.wait_for_timeout(3000); shot("UI_lab", 1400)
    pg.get_by_role("radio", name="Compare", exact=True).click(); pg.wait_for_timeout(4000); shot("UI_compare", 1380)
    pg.get_by_role("radio", name="Proof", exact=True).click(); pg.wait_for_timeout(16000); shot("UI_proof", 1500)
    b.close()
