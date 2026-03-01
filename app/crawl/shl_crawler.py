import json
import re
import os
from dataclasses import dataclass, asdict
from typing import List, Optional, Set
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright
import httpx

SITEMAP = "https://www.shl.com/sitemap/"
CATALOG = "https://www.shl.com/solutions/products/product-catalog/"
ALT_CATALOG = "https://www.shl.com/products/product-catalog/"


@dataclass
class SHLItem:
    url: str
    name: str
    adaptive_support: str
    description: str
    duration: int
    remote_support: str
    test_type: List[str]


def _text(handle) -> str:
    try:
        return (handle.inner_text() or "").strip()
    except Exception:
        return ""


def _attr(handle, name: str) -> Optional[str]:
    try:
        return handle.get_attribute(name)
    except Exception:
        return None


def is_individual_test_solution(card_text: str, category_text: str) -> bool:
    txt = (category_text or card_text).lower()
    return ("pre-packaged" not in txt) and ("job solution" not in txt)


def parse_card(card, base_url: str) -> Optional[SHLItem]:
    a = card.query_selector("a[href]")
    if not a:
        return None
    href = _attr(a, "href") or ""
    url = href if href.startswith("http") else urljoin(base_url, href)
    name = _text(a)

    desc_el = card.query_selector(".card-text, .description")
    description = _text(desc_el) if desc_el else ""

    full_text = card.inner_text()
    duration = 0
    m = re.search(r"duration[^0-9]*([0-9]{1,3})", full_text, flags=re.I)
    if m:
        try:
            duration = int(m.group(1))
        except Exception:
            duration = 0

    category_el = card.query_selector(".category")
    category_text = _text(category_el) if category_el else ""
    if not is_individual_test_solution(full_text, category_text):
        return None

    tags = []
    for t in card.query_selector_all(".tag, .badge"):
        txt = _text(t)
        if txt:
            tags.append(txt)

    adaptive = "No"
    remote = "Yes"

    return SHLItem(
        url=url,
        name=name,
        adaptive_support=adaptive,
        description=description,
        duration=duration,
        remote_support=remote,
        test_type=tags or [],
    )


def _get_meta(page, key: str) -> str:
    val = ""
    for sel in [f"meta[name='{key}']", f"meta[property='{key}']"]:
        try:
            el = page.locator(sel).first
            if el and el.count() > 0:
                c = el.get_attribute("content") or ""
                if c:
                    val = c.strip()
                    if val:
                        return val
        except Exception:
            continue
    return val


def _extract_name(page) -> str:
    for sel in ["h1", "title"]:
        try:
            el = page.locator(sel).first
            if el and el.count() > 0:
                t = el.inner_text().strip()
                if t:
                    if sel == "title" and " | " in t:
                        t = t.split(" | ")[0].strip()
                    return t
        except Exception:
            continue
    t = _get_meta(page, "og:title") or _get_meta(page, "title")
    return t.strip() if t else ""


def _extract_description(page) -> str:
    t = _get_meta(page, "description") or _get_meta(page, "og:description")
    if t:
        return t.strip()
    try:
        p = page.locator("p").first
        if p and p.count() > 0:
            txt = p.inner_text().strip()
            return txt
    except Exception:
        pass
    return ""


def _extract_duration(page_text: str) -> int:
    m = re.search(r"([0-9]{1,3})\s*(minutes|min|mins)\b", page_text, flags=re.I)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return 0
    m2 = re.search(r"duration[^0-9]*([0-9]{1,3})", page_text, flags=re.I)
    if m2:
        try:
            return int(m2.group(1))
        except Exception:
            return 0
    return 0


def _extract_types(page_text: str) -> List[str]:
    known = [
        "Knowledge & Skills",
        "Ability & Aptitude",
        "Competencies",
        "Personality & Behavior",
        "Biodata & Situational Judgement",
    ]
    out = []
    for k in known:
        if k.lower() in page_text.lower():
            out.append(k)
    return list(dict.fromkeys(out))


def crawl() -> List[SHLItem]:
    print("Starting crawl...")
    items: List[SHLItem] = []
    seen: Set[str] = set()
    product_urls: List[str] = []

    # First attempt: sitemap harvesting via direct HTTP (faster and less brittle)
    try:
        tops = [
            "https://www.shl.com/sitemap.xml",
            "https://www.shl.com/sitemap_index.xml",
            "https://www.shl.com/sitemap-index.xml",
        ]
        def fetch(url: str) -> str:
            try:
                r = httpx.get(url, timeout=20.0, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"})
                if r.status_code == 200:
                    return r.text
            except Exception:
                return ""
            return ""
        def locs_from(text: str) -> List[str]:
            return re.findall(r"<loc>(.*?)</loc>", text, flags=re.I | re.S)
        queue: List[str] = []
        for t in tops:
            q = fetch(t)
            if q:
                queue.extend(locs_from(q))
        for sect in range(1, 16):
            for loc in ["en_US", "en_IN", "en_AE", "en_ZA"]:
                queue.append(f"https://www.shl.com/sitemap.xml/sitemap/SilverStripe-CMS-Model-SiteTree/{sect}?l={loc}")
        visited_sm: Set[str] = set()
        while queue and len(product_urls) < 600:
            sm = queue.pop(0)
            if sm in visited_sm:
                continue
            visited_sm.add(sm)
            txt = fetch(sm)
            if not txt:
                continue
            locs = locs_from(txt)
            for loc in locs:
                u = loc.strip()
                ul = u.lower()
                if u.endswith(".xml"):
                    if u not in visited_sm and len(queue) < 500:
                        queue.append(u)
                    continue
                if "/product-catalog/" in ul and "/view/" in ul and "pre-packaged" not in ul:
                    u = u.split("?", 1)[0].split("#", 1)[0]
                    if u not in seen:
                        seen.add(u)
                        product_urls.append(u)
        if product_urls:
            print(f"Total product URLs found (via sitemaps httpx): {len(product_urls)}")
    except Exception:
        pass

    try:
        queries = list("abcdefghijklmnopqrstuvwxyz") + ["java", "python", "cognitive", "ability", "competency", "behaviour", "behavior", "personality", "aptitude", "situational", "programming", "skills"]
        def collect_search(q: str) -> List[str]:
            urls: List[str] = []
            for base in ["https://www.shl.com/?s=", "https://www.shl.com/search/"]:
                url = base + q if base.endswith("=") else base + q + "/"
                try:
                    r = httpx.get(url, timeout=15.0)
                    if r.status_code != 200:
                        continue
                    txt = r.text
                    for m in re.findall(r'href=["\\\']([^"\\\']+)', txt, flags=re.I):
                        try:
                            v = m if m.startswith("http") else urljoin(url, m)
                            vl = v.lower()
                            if "/product-catalog/" not in vl or "/view/" not in vl:
                                continue
                            if "pre-packaged" in vl:
                                continue
                            v = v.split("?", 1)[0].split("#", 1)[0]
                            urls.append(v)
                        except Exception:
                            continue
                except Exception:
                    continue
            return urls
        for q in queries:
            found = collect_search(q)
            for u in found:
                if u not in seen:
                    seen.add(u)
                    product_urls.append(u)
        if product_urls:
            print(f"Total product URLs found (via site search): {len(product_urls)}")
    except Exception:
        pass

    with sync_playwright() as p:
        headful = os.getenv("HEADFUL", "0") == "1"
        browser = p.chromium.launch(headless=not headful)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = ctx.new_page()
        page.set_default_timeout(30000)

        def accept_cookies(pg):
            try:
                selectors = [
                    "button:has-text('Accept')",
                    "button:has-text('I Agree')",
                    "button:has-text('I accept')",
                    "button:has-text('OK')",
                    "text=Accept all",
                ]
                for s in selectors:
                    loc = pg.locator(s)
                    if loc.count() > 0:
                        loc.first.click()
                        pg.wait_for_timeout(500)
                        break
            except Exception:
                pass

        def collect_from_catalog(pg, base_url: str) -> List[str]:
            collected: List[str] = []
            seen_local: Set[str] = set()
            def on_resp(resp):
                try:
                    url = resp.url or ""
                    ct = (resp.headers or {}).get("content-type", "")
                    if "json" in (ct or "").lower() or "api" in url.lower():
                        txt = ""
                        try:
                            txt = resp.text() or ""
                        except Exception:
                            txt = ""
                        if txt:
                            for m in re.findall(r'(/products?/product-catalog/[^"\\s]+/view/[^"\\s]+)', txt, flags=re.I):
                                try:
                                    u = m if m.startswith("http") else urljoin(base_url, m)
                                    ul = u.lower()
                                    if "/product-catalog/" not in ul or "/view/" not in ul:
                                        continue
                                    if "pre-packaged" in ul:
                                        continue
                                    if "?" in u:
                                        continue
                                    if u in seen or u in seen_local:
                                        continue
                                    seen_local.add(u)
                                    collected.append(u)
                                except Exception:
                                    continue
                except Exception:
                    pass
            try:
                pg.goto(base_url, wait_until="domcontentloaded")
                try:
                    pg.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                accept_cookies(pg)
                pg.on("response", on_resp)
                # Try clicking load/show more while links keep increasing
                last_count = -1
                stable_rounds = 0
                for _ in range(80):
                    try:
                        btn = pg.locator("button:has-text('Load more'), a:has-text('Load more'), button:has-text('Show more'), a:has-text('Show more')")
                        if btn.count() > 0:
                            btn.first.click()
                            pg.wait_for_timeout(900)
                    except Exception:
                        pass
                    # Scroll chunk
                    try:
                        pg.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                    except Exception:
                        pass
                    pg.wait_for_timeout(900)
                    # Extract anchors each round
                    hrefs_round = []
                    try:
                        hrefs_round = pg.evaluate(
                            """() => Array.from(document.querySelectorAll('a'))
                                  .map(a => a.getAttribute('href') || '')
                                  .filter(Boolean)"""
                        ) or []
                    except Exception:
                        hrefs_round = []
                    # Also read direct anchor locator for view links
                    try:
                        loc = pg.locator("a[href*='/product-catalog/'][href*='/view/']")
                        cnt = loc.count()
                    except Exception:
                        cnt = 0
                    for i in range(cnt):
                        try:
                            href = loc.nth(i).get_attribute("href") or ""
                            if not href:
                                continue
                            u = href if href.startswith("http") else urljoin(base_url, href)
                            ul = u.lower()
                            if "/product-catalog/" not in ul or "/view/" not in ul:
                                continue
                            if "pre-packaged" in ul:
                                continue
                            if "?" in u:
                                continue
                            if u in seen or u in seen_local:
                                continue
                            seen_local.add(u)
                            collected.append(u)
                        except Exception:
                            continue
                    for href in hrefs_round:
                        u = href if href.startswith("http") else urljoin(base_url, href)
                        ul = u.lower()
                        if "/product-catalog/" not in ul:
                            continue
                        if "/view/" not in ul:
                            continue
                        if "pre-packaged" in ul:
                            continue
                        if "?" in u:
                            continue
                        if u in seen or u in seen_local:
                            continue
                        seen_local.add(u)
                        collected.append(u)
                    if len(collected) == last_count:
                        stable_rounds += 1
                    else:
                        stable_rounds = 0
                    last_count = len(collected)
                    if stable_rounds >= 8:
                        break
            except Exception:
                pass
            return collected
        def collect_paginated(pg, base_url: str, max_pages: int = 60) -> List[str]:
            out: List[str] = []
            for i in range(1, max_pages + 1):
                try:
                    url = base_url.rstrip("/") + f"/page/{i}/"
                    pg.goto(url, wait_until="domcontentloaded")
                    accept_cookies(pg)
                    try:
                        pg.wait_for_load_state("networkidle", timeout=8000)
                    except Exception:
                        pass
                    hrefs = []
                    try:
                        hrefs = pg.evaluate(
                            """() => Array.from(document.querySelectorAll('a'))
                                  .map(a => a.getAttribute('href') || '')
                                  .filter(Boolean)"""
                        ) or []
                    except Exception:
                        hrefs = []
                    try:
                        loc = pg.locator("a[href*='/product-catalog/'][href*='/view/']")
                        cnt = loc.count()
                        for j in range(cnt):
                            try:
                                h = loc.nth(j).get_attribute("href") or ""
                                if h:
                                    hrefs.append(h)
                            except Exception:
                                continue
                    except Exception:
                        pass
                    for h in hrefs:
                        try:
                            u = h if h.startswith("http") else urljoin(url, h)
                            ul = u.lower()
                            if "/product-catalog/" not in ul or "/view/" not in ul:
                                continue
                            if "pre-packaged" in ul:
                                continue
                            if "?" in u:
                                continue
                            if u in seen:
                                continue
                            seen.add(u)
                            out.append(u)
                        except Exception:
                            continue
                except Exception:
                    continue
            return out
        page.goto(SITEMAP, wait_until="networkidle")
        html = ""
        try:
            html = page.content() or ""
        except Exception:
            html = ""
        # Regex-based extraction for resilience
        hrefs = re.findall(r'href=["\\\']([^"\\\']+)', html, flags=re.I)
        for href in hrefs:
            u = href if href.startswith("http") else urljoin(SITEMAP, href)
            ul = u.lower()
            # accept both /solutions/products/product-catalog/ and /products/product-catalog/
            if "/product-catalog/" not in ul:
                continue
            if "/view/" not in ul:
                continue
            if "pre-packaged" in ul:
                continue
            if "?" in u:
                continue
            if u in seen:
                continue
            seen.add(u)
            product_urls.append(u)
        # Fallback to DOM links if regex found nothing
        if not product_urls:
            anchors = page.locator("a")
            try:
                n = anchors.count()
            except Exception:
                n = 0
            for i in range(n):
                try:
                    a = anchors.nth(i)
                    href = a.get_attribute("href") or ""
                    if not href:
                        continue
                    u = href if href.startswith("http") else urljoin(SITEMAP, href)
                    ul = u.lower()
                    if "/product-catalog/" not in ul:
                        continue
                    if "/view/" not in ul:
                        continue
                    if "pre-packaged" in ul:
                        continue
                    # canonicalize query fragments instead of skipping
                    if "?" in u or "#" in u:
                        u = u.split("?", 1)[0].split("#", 1)[0]
                    if u in seen:
                        continue
                    seen.add(u)
                    product_urls.append(u)
                except Exception:
                    continue
        print(f"Total product URLs found: {len(product_urls)}")

        if not product_urls:
            try:
                def fetch_xml(url: str) -> str:
                    try:
                        r = page.request.get(url, timeout=20000)
                        if r and r.ok:
                            return r.text()
                    except Exception:
                        return ""
                    return ""

                def parse_locs(xml_text: str) -> List[str]:
                    return re.findall(r"<loc>(.*?)</loc>", xml_text, flags=re.I | re.S)

                # Try robots.txt for sitemap hints
                robots = fetch_xml("https://www.shl.com/robots.txt")
                sitemap_urls = []
                if robots:
                    for line in robots.splitlines():
                        line = line.strip()
                        if line.lower().startswith("sitemap:"):
                            sitemap_urls.append(line.split(":", 1)[1].strip())
                # Fallback known sitemap endpoints
                if not sitemap_urls:
                    sitemap_urls = [
                        "https://www.shl.com/sitemap.xml",
                        "https://www.shl.com/sitemap_index.xml",
                        "https://www.shl.com/sitemap-index.xml",
                    ]

                locs = []
                for x in sitemap_urls:
                    t = fetch_xml(x)
                    if t:
                        locs.extend(parse_locs(t))

                child_sitemaps = []
                for loc in locs:
                    u = loc.strip()
                    ul = u.lower()
                    # collect product-catalog view links directly from top-level sitemaps
                    if "/product-catalog/" in ul and "/view/" in ul and "pre-packaged" not in ul and "?" not in u:
                        if u not in seen:
                            seen.add(u)
                            product_urls.append(u)
                    elif u.endswith(".xml"):
                        child_sitemaps.append(u)

                for sm in child_sitemaps[:100]:
                    t2 = fetch_xml(sm)
                    if not t2:
                        continue
                    locs2 = parse_locs(t2)
                    for loc in locs2:
                        u = loc.strip()
                        ul = u.lower()
                        if "/product-catalog/" not in ul:
                            continue
                        if "/view/" not in ul:
                            continue
                        if "pre-packaged" in ul:
                            continue
                        if "?" in u or "#" in u:
                            u = u.split("?", 1)[0].split("#", 1)[0]
                        if u in seen:
                            continue
                        seen.add(u)
                        product_urls.append(u)
                print(f"Total product URLs found (from sitemaps): {len(product_urls)}")
            except Exception:
                pass

        if not product_urls:
            urls_solutions = collect_from_catalog(page, CATALOG)
            for u in urls_solutions:
                if u not in seen:
                    seen.add(u)
                    product_urls.append(u)
            print(f"Total product URLs found (from catalog scroll): {len(product_urls)}")
        if not product_urls:
            urls_alt = collect_from_catalog(page, ALT_CATALOG)
            for u in urls_alt:
                if u not in seen:
                    seen.add(u)
                    product_urls.append(u)
            print(f"Total product URLs found (from alternate catalog scroll): {len(product_urls)}")
        if len(product_urls) < 350:
            extra = collect_paginated(page, CATALOG, max_pages=80)
            for u in extra:
                if u not in seen:
                    seen.add(u)
                    product_urls.append(u)
            print(f"Total product URLs found (from paginated catalog): {len(product_urls)}")
        if len(product_urls) < 350:
            extra2 = collect_paginated(page, ALT_CATALOG, max_pages=80)
            for u in extra2:
                if u not in seen:
                    seen.add(u)
                    product_urls.append(u)
            print(f"Total product URLs found (from alternate paginated catalog): {len(product_urls)}")

        # Expand discovery by visiting product pages and harvesting more product links (BFS)
        to_visit: List[str] = product_urls[:]
        visited: Set[str] = set()
        idx = 0
        target_min = 500
        while idx < len(to_visit):
            u = to_visit[idx]
            idx += 1
            if u in visited:
                continue
            visited.add(u)
            try:
                page.goto(u, wait_until="domcontentloaded")
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                # Extract item fields
                name = _extract_name(page) or u
                description = _extract_description(page)
                full_text = ""
                try:
                    full_text = page.content()
                except Exception:
                    full_text = ""
                duration = _extract_duration(full_text)
                types = _extract_types(full_text)
                adaptive = "Yes" if re.search(r"\badaptive\b", full_text, flags=re.I) else "No"
                remote = "Yes" if re.search(r"\b(remote|online)\b", full_text, flags=re.I) else "Yes"
                items.append(
                    SHLItem(
                        url=u,
                        name=name,
                        adaptive_support=adaptive,
                        description=description,
                        duration=duration,
                        remote_support=remote,
                        test_type=types,
                    )
                )
                # Harvest more product links from this page
                hrefs_pg = []
                try:
                    hrefs_pg = page.evaluate(
                        """() => Array.from(document.querySelectorAll('a'))
                              .map(a => a.getAttribute('href') || '')
                              .filter(Boolean)"""
                    ) or []
                except Exception:
                    hrefs_pg = []
                for href in hrefs_pg:
                    try:
                        v = href if href.startswith("http") else urljoin(u, href)
                        vl = v.lower()
                        if "/product-catalog/" not in vl:
                            continue
                        if "/view/" not in vl:
                            continue
                        if "pre-packaged" in vl:
                            continue
                        if "?" in v or "#" in v:
                            v = v.split("?", 1)[0].split("#", 1)[0]
                        if v in seen:
                            continue
                        seen.add(v)
                        to_visit.append(v)
                    except Exception:
                        continue
                if len(items) % 25 == 0:
                    print(f"Items collected so far: {len(items)} | Queue size: {len(to_visit)}")
                if len(items) >= target_min:
                    break
            except Exception:
                continue

        browser.close()

    print(f"Final saved count: {len(items)}")
    if len(items) < 377:
        print("Warning: fewer than 377 items collected.")
    return items


def save(items: List[SHLItem], out_path: str):
    data = [asdict(it) for it in items]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    data = crawl()
    save(data, "catalog.json")
    print(f"Saved {len(data)} items")
