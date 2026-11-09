"""Read-only Chromium checks. Start `python -m http.server 8765 --bind 127.0.0.1` first.

Run: python tools/check_kempe_thill.py --output <screenshot-directory>
Requires Pillow and Playwright with Chromium installed. Never opens edit mode or writes remotely.
"""
import argparse
import json
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8765")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--thumbnail", action="store_true", help="Refresh local board thumbnail from page top.")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parent.parent
    data = json.loads((repo / "html/kempe-thill/data.json").read_text(encoding="utf-8"))
    report = {"pages": [], "screenshots": [], "interactions": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        def inspect(path, width, name):
            page = browser.new_page(viewport={"width": width, "height": 1000}, device_scale_factor=1)
            errors, missing, failed = [], [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.on("response", lambda response: missing.append({"url": response.url, "status": response.status}) if response.status >= 400 else None)
            page.on("requestfailed", lambda request: failed.append({"url": request.url, "error": request.failure}))
            page.goto(args.base + path, wait_until="networkidle")
            return page, {"page": name, "width": width, "console_errors": errors, "http_errors": missing, "failed_requests": failed}

        def screenshot(page, name, full=False):
            out = args.output / name
            page.screenshot(path=str(out), full_page=full)
            report["screenshots"].append(str(out.resolve()))

        def section_top(page, selector):
            page.locator(selector).evaluate("el => scrollTo(0, scrollY + el.getBoundingClientRect().top - (innerWidth > 760 ? 100 : 10))")

        def check_images(page, result):
            # Load every lazy image, including those outside initial viewport.
            page.eval_on_selector_all("img", "images => images.forEach(i => i.loading = 'eager')")
            page.wait_for_function("Array.from(document.images).every(i => i.complete)")
            result["broken_images"] = page.eval_on_selector_all("img", "images => images.filter(i => i.getAttribute('src') && !i.naturalWidth).map(i => i.src)")
            result["images"] = page.locator("img").count()

        def finish(page, result):
            result["horizontal_scroll"] = page.evaluate("document.documentElement.scrollWidth > innerWidth")
            report["pages"].append(result)
            assert not result["console_errors"], result
            assert not result["http_errors"], result
            assert not result["failed_requests"], result
            assert not result.get("broken_images"), result
            assert not result["horizontal_scroll"], result
            page.close()

        for width in (1440, 390):
            page, result = inspect("/html/kempe-thill/index.html", width, "Kempe Thill")
            page.wait_for_selector("#taste-plane .dot")
            assert page.locator("#taste-plane .dot").count() == 54
            assert page.locator("#reference-grid article").count() == 18
            assert page.locator("#load-error").is_hidden()
            check_images(page, result)
            screenshot(page, f"kempe-thill-{width}.png")
            screenshot(page, f"kempe-thill-{width}-full.png", full=True)
            section_top(page, "#taste")
            screenshot(page, f"kempe-thill-{width}-taste.png")

            for rating in ("liebt", "respektiert", "lehnt ab", "tib", "alle"):
                page.locator(f'#taste-filters button[data-filter="{rating}"]').click()
                expected = sum(rating == "alle" or (it["kind"] == "tib" if rating == "tib" else it["urteil"] == rating and it["kind"] != "tib") for it in data["taste"])
                assert page.locator("#taste-plane .dot:visible").count() == expected
                assert page.locator("#taste-select option").count() == expected
            page.locator("#taste-select").select_option(str(next(i for i, it in enumerate(data["taste"]) if it["id"] == "kt-fribourg")))
            assert "Fribourg" in page.locator("#taste-detail").inner_text()
            assert page.locator('#taste-detail a[href="https://atelierkempethill.com/projects/0099-university-library/"]').count() >= 1

            group = "Umbau Nachkriegsmoderne"
            page.locator(f'#mindmap [data-group="{group}"]').focus()
            page.keyboard.press("Enter")
            expected = sum(p["gruppe"] == group for p in data["projects"])
            assert page.locator("#map-projects button").count() == expected
            assert page.locator("#project-table tbody tr").count() == expected
            page.locator("#map-projects button").first.click()
            assert page.locator("#project-detail").is_visible()
            page.locator('#project-groups button[data-group=""]').click()
            page.locator("#all-projects").click()
            assert page.locator("#project-table tbody tr").count() == len(data["projects"])
            if width == 390:
                assert page.locator(".table-wrap").evaluate("el => el.scrollWidth <= el.clientWidth")
                assert page.locator("#mindmap svg").get_attribute("viewBox") == "0 0 400 790"
            page.locator('button[data-sort="jahr"]').click()
            first_sort = page.locator("#project-table tbody tr").evaluate_all("rows => rows.map(r => r.dataset.slug)")
            page.locator('button[data-sort="jahr"]').click()
            second_sort = page.locator("#project-table tbody tr").evaluate_all("rows => rows.map(r => r.dataset.slug)")
            assert first_sort != second_sort
            assert page.locator('th[aria-sort="descending"] button[data-sort="jahr"]').count() == 1
            page.locator("#project-search").fill("Fribourg")
            assert page.locator("#project-table tbody tr").count() == 1
            assert "Fribourg" in page.locator("#project-table tbody").inner_text()
            page.locator("#project-search").fill("zz-no-project-zz")
            assert "Keine Projekte gefunden" in page.locator("#project-table tbody").inner_text()
            page.locator("#project-search").fill("")
            section_top(page, "#projekte")
            screenshot(page, f"kempe-thill-{width}-atlas.png")
            # New dynamic detail images must load too.
            check_images(page, result)
            report["interactions"].append(f"{width}px: taste filters, selection/source, keyboard mindmap, project detail, 142 table rows, sort, search/empty state")
            finish(page, result)

            page, result = inspect("/html/referenzen/index.html?filter=kt#fribourg-bcu", width, "References · KT deep link")
            page.wait_for_selector("article.ref")
            assert page.locator('button[data-f="kt"][aria-pressed="true"]').count() == 1
            assert page.locator("article.ref").count() == 10
            assert page.locator("#fribourg-bcu").count() == 1
            check_images(page, result)
            page.locator("#fribourg-bcu").scroll_into_view_if_needed()
            screenshot(page, f"referenzen-kt-{width}.png")
            page.locator("#fribourg-bcu figure[data-role=eg] .box").click()
            assert page.locator("#lb").is_visible()
            page.wait_for_function("document.getElementById('lbimg').complete && document.getElementById('lbimg').naturalWidth > 0")
            assert page.locator("#lbsrc").get_attribute("href") == "https://atelierkempethill.com/projects/0099-university-library/"
            page.locator("#lbclose").click()
            # Deep-link filter survives reload, and normal category filtering remains usable.
            page.reload(wait_until="networkidle")
            assert page.locator("article.ref").count() == 10
            page.locator('button[data-f="alle"]').click()
            assert page.locator("article.ref").count() > 10
            page.locator('button[data-f="kt"]').click()
            report["interactions"].append(f"{width}px: KT filter/deep link/reload, tags, floor-plan lightbox and credit")
            finish(page, result)

        if args.thumbnail:
            page, result = inspect("/html/kempe-thill/index.html", 2000, "Board thumbnail")
            page.set_viewport_size({"width": 2000, "height": 1400})
            page.wait_for_selector("#taste-plane .dot")
            check_images(page, result)
            out = args.output / "kempe-thill-2000.png"
            page.screenshot(path=str(out))
            Image.open(out).convert("RGB").save(repo / "thumbs/kempe-thill.webp", "WEBP", quality=84, method=6)
            finish(page, result)

        page, result = inspect("/index.html", 1440, "Board")
        page.wait_for_selector("#world > .card")
        tile = page.locator("#world > .card").filter(has=page.locator('.cap:text-is("Kempe Thill · Büro + Haltung")'))
        assert tile.count() == 1
        image = tile.locator(".media img")
        image.evaluate("i => i.loading = 'eager'")
        image.evaluate("i => i.decode()")
        assert image.get_attribute("src") == "thumbs/kempe-thill.webp"
        # The tile must be reachable through normal pointer events, with no overlapping board item.
        image_box = image.bounding_box()
        assert image_box
        assert page.evaluate("p => document.elementFromPoint(p.x,p.y)?.closest('.card')?.item?.id", {"x": image_box["x"] + image_box["width"] / 2, "y": image_box["y"] + image_box["height"] / 2}) == "html/kempe-thill/index.html"
        screenshot(page, "board-1440.png")
        tile.click()
        frame = page.frame_locator('#ovbody > iframe')
        frame.locator("#taste-plane .dot").first.wait_for()
        assert frame.locator("h1").inner_text().startswith("Ordnung")
        report["interactions"].append("Board: thumbnail loads; tile opens Kempe Thill page in iframe")
        finish(page, result)
        browser.close()

    report["page_bytes"] = sum(p.stat().st_size for p in (repo / "html/kempe-thill").rglob("*") if p.is_file())
    assert report["page_bytes"] < 15_000_000
    dimensions = {p.name: list(Image.open(p).size) for p in (repo / "html/kempe-thill/img").glob("*.webp")}
    assert all(max(size) <= 1600 for size in dimensions.values())
    report["image_dimensions"] = dimensions
    (args.output / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
