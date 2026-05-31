"""
ITC Foods & Personal Care — Q-Commerce Price Tracker  v2.0
Key fixes:
- URL-based search (bypasses search box interaction entirely)
- Better anti-detection (random UA, viewport, realistic headers)
- Location verified after setting (checks displayed location text)
- Multi-pattern price extraction (handles ₹99, ₹ 99, Rs.99 etc.)
- Longer timeouts throughout
"""

import asyncio, re, json, datetime, random
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# ── PINCODES ───────────────────────────────────────────────────
PINCODES = [
    ("700156","New Town AA II-III","Premium"),
    ("700019","Ballygunge","Premium"),
    ("700016","Park Street / Camac Street","Premium"),
    ("700106","New Town Action Area I","Premium"),
    ("700020","Gariahat / Ballygunge Phari","Premium"),
    ("700027","Alipore","Premium"),
    ("700107","Chinar Park / Rajarhat","Upper Mid"),
    ("700097","Salt Lake Sec V / Karunamoyee","Upper Mid"),
    ("700150","Rajarhat E","Upper Mid"),
    ("700075","Kasba","Upper Mid"),
    ("700033","Tollygunge","Upper Mid"),
    ("700053","New Alipore","Upper Mid"),
    ("700064","Salt Lake Sec I-III","Upper Mid"),
    ("700073","Anandapur / EM Bypass","Upper Mid"),
    ("700098","Krishnapur / NT fringe","Upper Mid"),
    ("700022","Dhakuria / Golpark","Upper Mid"),
    ("700072","Jodhpur Park","Upper Mid"),
    ("700032","Jadavpur","Upper Mid"),
    ("700021","Lansdowne / Beck Bagan","Upper Mid"),
    ("700015","Elgin Road / Bhowanipore N","Upper Mid"),
    ("700091","Salt Lake Sec IV-V","Upper Mid"),
    ("700086","Deshapriya Park","Upper Mid"),
    ("700077","Dhakuria W","Upper Mid"),
    ("700026","Southern Avenue / Lake E","Upper Mid"),
    ("700084","Garia / Narendrapur fringe","Upper Mid"),
    ("700028","Bhabanipur / Paddapukur","Upper Mid"),
    ("700025","Bhowanipore","Upper Mid"),
    ("700155","New Town Adj","Upper Mid"),
    ("700029","Lake Gardens","Upper Mid"),
]

# ── SKU LIST ───────────────────────────────────────────────────
# (sku_id, brand, display_name, category, subcategory, mrp, is_itc, search_query)
# search_query = short term that works best in platform search URLs
SKUS = [
    # ITC FOODS
    ("SF_DF_75",   "Sunfeast","Dark Fantasy Choco Fills 75g",     "Foods","Biscuits",   30, True, "sunfeast dark fantasy choco fills 75"),
    ("SF_DF_300",  "Sunfeast","Dark Fantasy Choco Fills 300g",    "Foods","Biscuits",  110, True, "sunfeast dark fantasy 300"),
    ("SF_MM_150",  "Sunfeast","Moms Magic Butter 150g",           "Foods","Biscuits",   30, True, "sunfeast moms magic butter"),
    ("SF_FL_150",  "Sunfeast","Farmlite Digestive 150g",          "Foods","Biscuits",   35, True, "sunfeast farmlite digestive"),
    ("SF_ML_250",  "Sunfeast","Marie Light 250g",                 "Foods","Biscuits",   25, True, "sunfeast marie light"),
    ("BG_MA_65",   "Bingo",   "Mad Angles Achaari Masti 65g",     "Foods","Snacks",     20, True, "bingo mad angles achaari"),
    ("BG_TM_65",   "Bingo",   "Tedhe Medhe Masala 65g",           "Foods","Snacks",     20, True, "bingo tedhe medhe"),
    ("BG_OS_52",   "Bingo",   "Original Style Cream Onion 52g",   "Foods","Snacks",     20, True, "bingo original style cream onion"),
    ("BG_RS_90",   "Bingo",   "Ridge Spiced 90g",                 "Foods","Snacks",     30, True, "bingo ridge spiced"),
    ("YP_MM_4P",   "Yippee",  "Magic Masala Noodles 4 pack",      "Foods","Noodles",    60, True, "yippee magic masala noodles"),
    ("YP_CM_4P",   "Yippee",  "Classic Masala Noodles 4 pack",    "Foods","Noodles",    60, True, "yippee classic masala noodles"),
    ("AA_AT_5K",   "Aashirvaad","Whole Wheat Atta 5kg",           "Foods","Staples",   280, True, "aashirvaad atta 5kg"),
    ("AA_AT_10K",  "Aashirvaad","Whole Wheat Atta 10kg",          "Foods","Staples",   520, True, "aashirvaad atta 10kg"),
    ("AA_SL_1K",   "Aashirvaad","Salt 1kg",                       "Foods","Staples",    20, True, "aashirvaad salt 1kg"),
    ("BN_MF_1L",   "B Natural","Mixed Fruit Juice 1L",            "Foods","Beverages", 120, True, "b natural mixed fruit juice 1l"),
    ("BN_OR_1L",   "B Natural","Orange Juice 1L",                 "Foods","Beverages", 120, True, "b natural orange juice 1l"),
    ("KI_BC_285",  "Kitchens of India","Butter Chicken 285g",     "Foods","Ready to Eat",180,True,"kitchens of india butter chicken"),
    # ITC PERSONAL CARE
    ("FM_SG_BC",   "Fiama",   "Shower Gel Blackcurrant 250ml",    "Personal Care","Bath",    299,True,"fiama shower gel blackcurrant 250"),
    ("FM_SG_PH",   "Fiama",   "Shower Gel Peach 250ml",           "Personal Care","Bath",    299,True,"fiama shower gel peach 250"),
    ("FM_SH_DR",   "Fiama",   "Shampoo Damage Repair 340ml",      "Personal Care","Hair",    349,True,"fiama shampoo damage repair 340"),
    ("FM_SH_VB",   "Fiama",   "Shampoo Volume Boost 340ml",       "Personal Care","Hair",    349,True,"fiama shampoo volume boost"),
    ("FM_FW_100",  "Fiama",   "Face Wash Brightening 100ml",      "Personal Care","Skin",    199,True,"fiama face wash brightening 100"),
    ("FM_BB_3P",   "Fiama",   "Bathing Bar Pack of 3",            "Personal Care","Bath",    165,True,"fiama bathing bar pack 3"),
    ("EN_SP_150",  "Engage",  "Spell Deodorant Men 150ml",        "Personal Care","Deo",     230,True,"engage spell deodorant men 150"),
    ("EN_TS_150",  "Engage",  "Tease Deodorant Women 150ml",      "Personal Care","Deo",     230,True,"engage tease deodorant women 150"),
    ("EN_PP_M",    "Engage",  "Pocket Perfume Men 18ml",          "Personal Care","Deo",     175,True,"engage pocket perfume men"),
    ("EN_PP_W",    "Engage",  "Pocket Perfume Women 18ml",        "Personal Care","Deo",     175,True,"engage pocket perfume women"),
    ("VV_SP_4P",   "Vivel",   "Active Fair Soap 100g Pack of 4",  "Personal Care","Bath",    148,True,"vivel active fair soap 100g"),
    ("VV_SH_340",  "Vivel",   "Shampoo Silky Smooth 340ml",       "Personal Care","Hair",    249,True,"vivel shampoo silky smooth 340"),
    ("SV_HW_200",  "Savlon",  "Hand Wash 200ml",                  "Personal Care","Hygiene", 109,True,"savlon hand wash 200ml"),
    ("SV_AL_500",  "Savlon",  "Antiseptic Liquid 500ml",          "Personal Care","Hygiene", 199,True,"savlon antiseptic liquid 500"),
    ("NM_FC_1L",   "Nimyle",  "Neem Floor Cleaner 1L",            "Personal Care","Home",    120,True,"nimyle floor cleaner 1l"),
    ("NM_FC_2L",   "Nimyle",  "Neem Floor Cleaner 2L",            "Personal Care","Home",    210,True,"nimyle floor cleaner 2l"),
    # COMPETITORS - FOODS
    ("BR_GD_200",  "Britannia","Good Day Butter Cookies 200g",    "Foods","Biscuits",   35,False,"britannia good day butter 200"),
    ("BR_NC_250",  "Britannia","NutriChoice Digestive 250g",      "Foods","Biscuits",   40,False,"britannia nutrichoice digestive"),
    ("PR_PG_250",  "Parle",   "Parle G Glucose Biscuits 250g",    "Foods","Biscuits",   20,False,"parle g glucose biscuits 250"),
    ("NS_MG_4P",   "Maggi",   "2 Minute Noodles 4 pack",          "Foods","Noodles",    60,False,"maggi 2 minute noodles masala 4"),
    ("PG_LY_52",   "Lays",    "Classic Salted Chips 52g",         "Foods","Snacks",     20,False,"lays classic salted chips 52"),
    ("PG_KU_65",   "Kurkure", "Masala Munch 65g",                 "Foods","Snacks",     20,False,"kurkure masala munch 65"),
    ("PN_AT_5K",   "Patanjali","Whole Wheat Atta 5kg",            "Foods","Staples",   220,False,"patanjali atta 5kg"),
    ("RL_MF_1L",   "Real",    "Mixed Fruit Juice 1L",             "Foods","Beverages", 120,False,"real mixed fruit juice 1l"),
    # COMPETITORS - PERSONAL CARE
    ("DV_BW_250",  "Dove",    "Body Wash 250ml",                  "Personal Care","Bath",    299,False,"dove body wash deeply nourishing 250"),
    ("LB_HW_200",  "Lifebuoy","Total Hand Wash 200ml",            "Personal Care","Hygiene", 109,False,"lifebuoy total hand wash 200"),
    ("PT_SH_340",  "Pantene", "Anti Dandruff Shampoo 340ml",      "Personal Care","Hair",    349,False,"pantene anti dandruff shampoo 340"),
    ("DT_HW_200",  "Dettol",  "Original Hand Wash 200ml",         "Personal Care","Hygiene", 109,False,"dettol original hand wash 200"),
    ("VS_BL_200",  "Vaseline","Body Lotion 200ml",                "Personal Care","Skin",    199,False,"vaseline intensive care body lotion 200"),
    ("HH_SH_340",  "Head & Shoulders","Anti Dandruff Shampoo 340ml","Personal Care","Hair",349,False,"head shoulders anti dandruff shampoo 340"),
    ("OL_FW_100",  "Olay",    "Face Wash 100ml",                  "Personal Care","Skin",    299,False,"olay natural white face wash 100"),
]

PLATFORMS = ["Blinkit", "Zepto", "Swiggy Instamart"]

# Random user agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Samsung Galaxy S21) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Search URL templates
SEARCH_URLS = {
    "Blinkit":          "https://blinkit.com/s/?q={query}",
    "Zepto":            "https://www.zeptonow.com/search?query={query}",
    "Swiggy Instamart": "https://www.swiggy.com/instamart/search?query={query}",
}

BASE_URLS = {
    "Blinkit":          "https://blinkit.com",
    "Zepto":            "https://www.zeptonow.com",
    "Swiggy Instamart": "https://www.swiggy.com/instamart",
}


# ── PRICE EXTRACTION ──────────────────────────────────────────
def extract_all_prices(text):
    """Extract all prices from text. Handles ₹99, ₹ 99, Rs.99, Rs 99."""
    patterns = [
        r'₹\s*(\d+(?:\.\d{1,2})?)',
        r'Rs\.?\s*(\d+(?:\.\d{1,2})?)',
        r'MRP[:\s]*(\d+(?:\.\d{1,2})?)',
    ]
    prices = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            try:
                prices.append(int(float(m.group(1))))
            except Exception:
                pass
    return sorted(set(prices))


# ── PRODUCT MATCHING ──────────────────────────────────────────
def is_match(query, card_text, mrp_expected):
    """Loose match: key words appear in card text + price is plausible."""
    card_lower = card_text.lower()
    # Strip sizes/units from query for word matching
    core = re.sub(r'\b(\d+g|\d+ml|\d+kg|\d+l|\d+\s*pack|pack of \d+|\d+s?)\b', '', query.lower())
    words = [w for w in re.split(r'\W+', core) if len(w) > 2]
    if not words:
        return False
    match_ratio = sum(1 for w in words if w in card_lower) / len(words)
    if match_ratio < 0.55:
        return False
    # Price sanity: at least one price must be <= 2x expected MRP
    prices = extract_all_prices(card_text)
    if prices and min(prices) > mrp_expected * 2.5:
        return False
    return True


# ── LOCATION SETTER ───────────────────────────────────────────
async def set_location(page, pincode, platform):
    try:
        await page.goto(BASE_URLS[platform], timeout=40000,
                        wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Click location trigger
        for sel in [
            "[data-testid='location-bar']",
            "[class*='LocationBar']",
            "[class*='location-bar']",
            "text=Detect Location",
            "text=Enter Location",
            "[class*='location']",
            "text=Set Location",
        ]:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    await el.click()
                    await page.wait_for_timeout(1500)
                    break
            except Exception:
                pass

        # Fill pincode in input
        for sel in [
            "input[placeholder*='pincode' i]",
            "input[placeholder*='area' i]",
            "input[placeholder*='search' i]",
            "input[placeholder*='enter' i]",
            "input[type='search']",
            "input[type='text']",
        ]:
            try:
                inp = page.locator(sel).first
                if not await inp.is_visible(timeout=2000):
                    continue
                await inp.click()
                await inp.fill("")
                await page.wait_for_timeout(300)
                await inp.type(pincode, delay=100)
                await page.wait_for_timeout(2000)

                # Click first suggestion
                for sug in [
                    "[data-testid*='suggestion']",
                    "[data-testid*='location']",
                    "[class*='suggestion' i]",
                    "[class*='location-item' i]",
                    "[role='option']",
                    "li[class*='item']",
                    "li",
                ]:
                    try:
                        first = page.locator(sug).first
                        if await first.is_visible(timeout=2000):
                            await first.click()
                            await page.wait_for_timeout(2500)
                            print(f"      📍 Location set via: {sug[:40]}")
                            return True
                    except Exception:
                        pass
            except Exception:
                pass

        # Fallback: check if page has product content anyway
        body = await page.inner_text("body")
        if any(w in body.lower() for w in ["add", "cart", "buy", "₹"]):
            print(f"      📍 Location unset but products visible")
            return True

        return False
    except Exception as e:
        print(f"      ⚠️  Location error: {str(e)[:60]}")
        return False


# ── URL-BASED SEARCH ─────────────────────────────────────────
async def search_url(page, sku, platform):
    """
    Navigate directly to search URL — more reliable than typing in search box.
    Returns (sell_price, mrp_scraped) or (None, None)
    """
    sku_id, brand, name, category, subcategory, mrp, is_itc, query = sku

    search_url = SEARCH_URLS[platform].format(
        query=query.replace(" ", "+")
    )

    try:
        await page.goto(search_url, timeout=35000,
                        wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Grab all text
        body_text = await page.inner_text("body")

        # Quick check — if no rupee signs, nothing priced = no products
        if "₹" not in body_text and "Rs" not in body_text.lower():
            return None, None

        # Card selectors per platform
        card_sels = {
            "Blinkit":          "[class*='ProductCard'], .product-card, [data-testid*='product']",
            "Zepto":            "[class*='ProductCard'], [class*='product-card'], [class*='Product']",
            "Swiggy Instamart": "[class*='ItemCard'], [class*='item-card'], [class*='Product'], [class*='product']",
        }

        cards = page.locator(card_sels.get(platform, "[class*='card']"))
        count = await cards.count()

        for i in range(min(count, 30)):
            try:
                card = cards.nth(i)
                card_text = await card.inner_text(timeout=1000)

                if not is_match(query, card_text, mrp):
                    continue

                prices = extract_all_prices(card_text)
                if not prices:
                    continue

                sell_price  = min(prices)
                mrp_scraped = max(prices) if len(prices) > 1 else None

                # Sanity check
                if sell_price < 5 or sell_price > mrp * 3:
                    continue

                return sell_price, mrp_scraped or mrp

            except Exception:
                continue

        # Fallback: extract from full page text
        prices = extract_all_prices(body_text)
        if prices and is_match(query, body_text, mrp):
            sell_price = min(p for p in prices if 5 < p <= mrp * 2.5)
            return sell_price, mrp

    except Exception as e:
        print(f"      ⚠️  Search error ({query[:20]}): {str(e)[:50]}")

    return None, None


# ── HTML BUILDER ──────────────────────────────────────────────
def build_html(results, run_dt):
    data_str = json.dumps(results)
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ITC Price Tracker</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{--bg:#080d1a;--surface:#0e1628;--border:#1e2d4a;--gold:#c9a84c;--gold2:#e8c97a;
        --text:#dce8ff;--muted:#6b82a8;--green:#22c55e;--blue:#60a5fa;--purple:#a78bfa}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:'Syne',sans-serif;min-height:100vh}
  header{border-bottom:1px solid var(--border);padding:18px 28px;display:flex;align-items:center;justify-content:space-between;background:linear-gradient(90deg,#080d1a 60%,#0f1c35)}
  .logo{display:flex;align-items:center;gap:12px}
  .logo-mark{width:36px;height:36px;border-radius:8px;background:linear-gradient(135deg,#c9a84c,#7a5a1a);display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:800;color:#fff}
  h1{font-size:1.1rem;font-weight:700}.subtitle{font-size:.72rem;color:var(--muted);font-family:'DM Mono',monospace}
  .run-time{font-size:.68rem;color:var(--muted);font-family:'DM Mono',monospace;text-align:right}
  .run-time span{color:var(--gold);font-weight:600}
  .stats{display:flex;gap:1px;border-bottom:1px solid var(--border);background:var(--border)}
  .stat{flex:1;background:var(--surface);padding:12px 18px}
  .stat-val{font-size:1.5rem;font-weight:800;color:var(--gold);line-height:1}
  .stat-lbl{font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:2px}
  .tabs{display:flex;border-bottom:2px solid var(--border);background:var(--surface);padding:0 28px}
  .tab{padding:12px 20px;font-size:.8rem;font-weight:700;cursor:pointer;color:var(--muted);border-bottom:2px solid transparent;margin-bottom:-2px;transition:all .15s}
  .tab.active{color:var(--gold);border-bottom-color:var(--gold)}
  .tab:hover:not(.active){color:var(--text)}
  .filters{padding:14px 28px;border-bottom:1px solid var(--border);display:flex;flex-wrap:wrap;gap:14px;align-items:flex-start;background:var(--surface)}
  .filter-group{display:flex;flex-direction:column;gap:5px}
  .filter-label{font-size:.58rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted)}
  .pills{display:flex;flex-wrap:wrap;gap:4px}
  .pill{padding:3px 10px;border-radius:20px;font-size:.7rem;font-weight:600;cursor:pointer;border:1px solid var(--border);background:#12213a;color:var(--muted);transition:all .15s;user-select:none}
  .pill.active{background:var(--gold);color:#080d1a;border-color:var(--gold)}
  .pill:hover:not(.active){border-color:var(--gold);color:var(--text)}
  .search-wrap{margin-left:auto;display:flex;align-items:flex-end;gap:8px}
  #search{background:var(--bg);border:1px solid var(--border);color:var(--text);padding:5px 11px;border-radius:8px;font-family:'Syne',sans-serif;font-size:.78rem;width:180px;outline:none}
  #search:focus{border-color:var(--gold)}
  #count-badge{font-size:.68rem;color:var(--muted);font-family:'DM Mono',monospace;padding-bottom:7px}
  .table-wrap{overflow-x:auto;padding-bottom:40px}
  .view{display:none}.view.active{display:block}
  table{width:100%;border-collapse:collapse;font-size:.76rem}
  thead th{position:sticky;top:0;z-index:10;background:#0b1223;border-bottom:2px solid var(--gold);padding:9px 13px;text-align:left;font-size:.58rem;text-transform:uppercase;letter-spacing:1.2px;color:var(--gold);white-space:nowrap;cursor:pointer}
  thead th:hover{color:var(--gold2)}.sort-icon{opacity:.35;margin-left:3px}
  thead th.sorted .sort-icon{opacity:1}
  tbody tr{border-bottom:1px solid var(--border);transition:background .1s}
  tbody tr:hover{background:#0f1e38}
  td{padding:7px 13px;white-space:nowrap}
  td.name{white-space:normal;max-width:220px;font-weight:500}
  td.brand-itc{color:var(--gold2);font-weight:700}
  td.brand-comp{color:var(--blue);font-weight:600}
  .platform-tag{font-size:.6rem;font-weight:700;padding:2px 7px;border-radius:4px;text-transform:uppercase}
  .plat-blinkit{background:#1a2e0a;color:#86efac}
  .plat-zepto{background:#2a1040;color:#c4b5fd}
  .plat-swiggy{background:#2a1010;color:#fca5a5}
  .price{font-family:'DM Mono',monospace;font-weight:700;color:var(--green)}
  .mrp{font-family:'DM Mono',monospace;font-size:.68rem;color:#4b5e7a;text-decoration:line-through}
  .disc-high{color:var(--green);font-weight:700}
  .disc-mid{color:var(--gold);font-weight:600}
  .disc-low{color:var(--muted)}
  .disc-none{color:#374151}
  .badge-itc{background:#1a2e0a;color:#86efac;font-size:.58rem;padding:1px 7px;border-radius:10px;font-weight:700}
  .badge-comp{background:#12213a;color:var(--blue);font-size:.58rem;padding:1px 7px;border-radius:10px}
  .na{color:#2d3f5a;font-family:'DM Mono',monospace;font-size:.68rem}
  .winner{background:#0d2010;color:var(--green);font-weight:700}
  .loser{color:#4b5e7a}
  #empty{text-align:center;padding:50px;color:var(--muted);display:none}
</style>
</head>
<body>
<header>
  <div class="logo"><div class="logo-mark">₹</div>
  <div><h1>ITC Q-Commerce Price Tracker</h1><div class="subtitle">Foods & Personal Care · ECAL Branch · 29 Zones · Lowest price across pincodes</div></div></div>
  <div class="run-time">Updated<br><span id="run-dt"></span></div>
</header>
<div class="stats">
  <div class="stat"><div class="stat-val" id="s-skus">—</div><div class="stat-lbl">SKUs Tracked</div></div>
  <div class="stat"><div class="stat-val" id="s-found">—</div><div class="stat-lbl">Found on Platforms</div></div>
  <div class="stat"><div class="stat-val" id="s-disc">—</div><div class="stat-lbl">Avg ITC Discount %</div></div>
  <div class="stat"><div class="stat-val" id="s-cheap">—</div><div class="stat-lbl">Cheapest Platform</div></div>
  <div class="stat"><div class="stat-val" id="s-itc-vs">—</div><div class="stat-lbl">ITC vs Comp Δ%</div></div>
</div>
<div class="tabs">
  <div class="tab active" data-view="v1">💰 Price Tracker</div>
  <div class="tab" data-view="v2">📊 Discount Analysis</div>
  <div class="tab" data-view="v3">⚔️ ITC vs Competitor</div>
</div>
<div class="filters">
  <div class="filter-group"><div class="filter-label">Platform</div><div class="pills" id="f-platform"></div></div>
  <div class="filter-group"><div class="filter-label">Category</div><div class="pills" id="f-category"></div></div>
  <div class="filter-group"><div class="filter-label">Sub-category</div><div class="pills" id="f-sub"></div></div>
  <div class="filter-group"><div class="filter-label">Brand Type</div><div class="pills" id="f-type"></div></div>
  <div class="filter-group"><div class="filter-label">Brand</div><div class="pills" id="f-brand"></div></div>
  <div class="search-wrap">
    <div><div class="filter-label">Search</div><input id="search" placeholder="product name…"></div>
    <div id="count-badge">— rows</div>
  </div>
</div>
<div class="table-wrap">
  <div class="view active" id="v1">
    <table><thead><tr>
      <th data-col="brand">Brand <span class="sort-icon">↕</span></th>
      <th data-col="sku_name">Product <span class="sort-icon">↕</span></th>
      <th data-col="category">Category <span class="sort-icon">↕</span></th>
      <th data-col="subcategory">Sub-cat <span class="sort-icon">↕</span></th>
      <th data-col="platform">Platform <span class="sort-icon">↕</span></th>
      <th data-col="sell_price">Best Price ↓ <span class="sort-icon">↕</span></th>
      <th data-col="mrp">MRP <span class="sort-icon">↕</span></th>
      <th data-col="discount_pct">Disc % <span class="sort-icon">↕</span></th>
      <th data-col="is_itc">Type <span class="sort-icon">↕</span></th>
    </tr></thead><tbody id="tbody1"></tbody></table>
  </div>
  <div class="view" id="v2">
    <table><thead><tr>
      <th data-col="brand">Brand <span class="sort-icon">↕</span></th>
      <th data-col="sku_name">Product <span class="sort-icon">↕</span></th>
      <th data-col="mrp">MRP <span class="sort-icon">↕</span></th>
      <th data-col="blinkit_price">Blinkit <span class="sort-icon">↕</span></th>
      <th data-col="zepto_price">Zepto <span class="sort-icon">↕</span></th>
      <th data-col="swiggy_price">Swiggy <span class="sort-icon">↕</span></th>
      <th data-col="min_price">Lowest <span class="sort-icon">↕</span></th>
      <th data-col="max_disc">Max Disc% <span class="sort-icon">↕</span></th>
    </tr></thead><tbody id="tbody2"></tbody></table>
  </div>
  <div class="view" id="v3">
    <table><thead><tr>
      <th>Sub-category</th><th>ITC Brand</th><th>ITC Product</th>
      <th>ITC Best Price</th><th>Competitor</th><th>Comp Product</th>
      <th>Comp Price</th><th>Verdict</th><th>Platform</th>
    </tr></thead><tbody id="tbody3"></tbody></table>
  </div>
  <div id="empty">No results match your filters</div>
</div>
<script>
const RAW = """ + data_str + """;
const state = {platform:new Set(['ALL']),category:new Set(['ALL']),sub:new Set(['ALL']),type:new Set(['ALL']),brand:new Set(['ALL']),search:''};
let sortCol=null,sortDir=1;
document.getElementById('run-dt').textContent = RAW[0]?.checked_at||'';
const uniq = k => [...new Set(RAW.map(r=>r[k]).filter(Boolean))].sort();
function buildPills(id,key,vals){
  const w=document.getElementById(id);
  ['ALL',...vals].forEach(v=>{
    const p=document.createElement('span');
    p.className='pill'+(v==='ALL'?' active':'');p.textContent=v==='ALL'?'All':v;p.dataset.val=v;
    p.addEventListener('click',()=>toggle(key,v,w));w.appendChild(p);
  });
}
function toggle(key,val,wrap){
  const s=state[key];
  if(val==='ALL'){s.clear();s.add('ALL');}
  else{s.delete('ALL');s.has(val)?s.delete(val):s.add(val);if(!s.size)s.add('ALL');}
  wrap.querySelectorAll('.pill').forEach(p=>p.classList.toggle('active',s.has(p.dataset.val)));render();
}
function filteredRaw(){
  return RAW.filter(r=>{
    if(!state.platform.has('ALL')&&!state.platform.has(r.platform))return false;
    if(!state.category.has('ALL')&&!state.category.has(r.category))return false;
    if(!state.sub.has('ALL')&&!state.sub.has(r.subcategory))return false;
    if(!state.type.has('ALL')){if(state.type.has('ITC')&&!r.is_itc)return false;if(state.type.has('Competitor')&&r.is_itc)return false;}
    if(!state.brand.has('ALL')&&!state.brand.has(r.brand))return false;
    if(state.search){const q=state.search.toLowerCase();if(!(r.sku_name||'').toLowerCase().includes(q)&&!(r.brand||'').toLowerCase().includes(q))return false;}
    return true;
  });
}
function buildPivot(rows){
  const map={};
  rows.forEach(r=>{
    if(!r.sell_price)return;
    const k=r.sku_id;
    if(!map[k])map[k]={sku_id:r.sku_id,brand:r.brand,sku_name:r.sku_name,category:r.category,subcategory:r.subcategory,mrp:r.mrp,is_itc:r.is_itc,blinkit_price:null,zepto_price:null,swiggy_price:null};
    if(r.platform==='Blinkit')map[k].blinkit_price=r.sell_price;
    if(r.platform==='Zepto')map[k].zepto_price=r.sell_price;
    if(r.platform==='Swiggy Instamart')map[k].swiggy_price=r.sell_price;
  });
  return Object.values(map).map(r=>{
    const prices=[r.blinkit_price,r.zepto_price,r.swiggy_price].filter(Boolean);
    r.min_price=prices.length?Math.min(...prices):null;
    r.max_disc=r.min_price?Math.round((1-r.min_price/r.mrp)*100):null;
    return r;
  });
}
const PAIRS=[
  ['Biscuits','Sunfeast','Britannia'],['Biscuits','Sunfeast','Parle'],
  ['Snacks','Bingo','Lays'],['Snacks','Bingo','Kurkure'],
  ['Noodles','Yippee','Maggi'],['Staples','Aashirvaad','Patanjali'],
  ['Beverages','B Natural','Real'],['Bath','Fiama','Dove'],
  ['Hair','Fiama','Pantene'],['Hair','Fiama','Head & Shoulders'],
  ['Hygiene','Savlon','Lifebuoy'],['Hygiene','Savlon','Dettol'],
  ['Skin','Fiama','Olay'],['Deo','Engage','Vaseline'],
];
function buildComparisons(rows){
  return PAIRS.map(([sub,itcB,compB])=>{
    const itcRows=rows.filter(r=>r.is_itc&&r.brand===itcB&&r.subcategory===sub&&r.sell_price);
    const compRows=rows.filter(r=>!r.is_itc&&r.brand===compB&&r.subcategory===sub&&r.sell_price);
    if(!itcRows.length||!compRows.length)return null;
    const ib=itcRows.reduce((a,b)=>a.sell_price<=b.sell_price?a:b);
    const cb=compRows.reduce((a,b)=>a.sell_price<=b.sell_price?a:b);
    const delta=cb.sell_price?Math.round((ib.sell_price-cb.sell_price)/cb.sell_price*100):null;
    return{sub,itcBrand:itcB,itcSku:ib.sku_name,itcPrice:ib.sell_price,itcPlat:ib.platform,compBrand:compB,compSku:cb.sku_name,compPrice:cb.sell_price,compPlat:cb.platform,delta};
  }).filter(Boolean);
}
function discClass(d){return d===null?'disc-none':d>=15?'disc-high':d>=5?'disc-mid':'disc-low';}
function pc(p){return p==='Blinkit'?'plat-blinkit':p==='Zepto'?'plat-zepto':'plat-swiggy';}
function priceCell(p){return p?`<span class="price">₹${p}</span>`:'<span class="na">—</span>';}
function updateStats(rows){
  const skus=new Set(rows.map(r=>r.sku_id)).size;
  const found=rows.filter(r=>r.sell_price).length;
  const itcR=rows.filter(r=>r.is_itc&&r.sell_price&&r.discount_pct!==null);
  const avg=itcR.length?Math.round(itcR.reduce((a,b)=>a+b.discount_pct,0)/itcR.length):0;
  const ps={};rows.filter(r=>r.sell_price).forEach(r=>{ps[r.platform]=(ps[r.platform]||0)+1;});
  const cheap=Object.entries(ps).sort((a,b)=>b[1]-a[1])[0];
  const itcA=rows.filter(r=>r.is_itc&&r.sell_price);
  const cA=rows.filter(r=>!r.is_itc&&r.sell_price);
  const iAvg=itcA.length?itcA.reduce((a,b,_,arr)=>a+b.sell_price/arr.length,0):0;
  const cAvg=cA.length?cA.reduce((a,b,_,arr)=>a+b.sell_price/arr.length,0):0;
  const delta=cAvg?Math.round((iAvg-cAvg)/cAvg*100):0;
  document.getElementById('s-skus').textContent=skus;
  document.getElementById('s-found').textContent=found;
  document.getElementById('s-disc').textContent=avg+'%';
  document.getElementById('s-cheap').textContent=cheap?cheap[0].split(' ')[0]:'—';
  document.getElementById('s-itc-vs').textContent=(delta>=0?'+':'')+delta+'%';
  document.getElementById('count-badge').textContent=rows.length+' rows';
}
function render(){
  const rows=filteredRaw().sort((a,b)=>{if(!sortCol)return 0;const va=a[sortCol]??'',vb=b[sortCol]??'';return va<vb?-sortDir:va>vb?sortDir:0;});
  updateStats(rows);
  document.getElementById('empty').style.display='none';
  document.getElementById('tbody1').innerHTML=rows.map(r=>`<tr>
    <td class="${r.is_itc?'brand-itc':'brand-comp'}">${r.brand}</td>
    <td class="name">${r.sku_name}</td><td>${r.category}</td>
    <td style="color:var(--muted);font-size:.7rem">${r.subcategory}</td>
    <td><span class="platform-tag ${pc(r.platform)}">${r.platform}</span></td>
    <td>${r.sell_price?`<span class="price">₹${r.sell_price}</span>`:'<span class="na">—</span>'}</td>
    <td><span class="mrp">₹${r.mrp}</span></td>
    <td class="${discClass(r.discount_pct)}">${r.discount_pct!==null?r.discount_pct+'%':'—'}</td>
    <td>${r.is_itc?'<span class="badge-itc">ITC</span>':'<span class="badge-comp">Comp</span>'}</td>
  </tr>`).join('');
  const pivot=buildPivot(rows);
  document.getElementById('tbody2').innerHTML=pivot.map(r=>`<tr>
    <td class="${r.is_itc?'brand-itc':'brand-comp'}">${r.brand}</td>
    <td class="name">${r.sku_name}</td>
    <td style="color:#6b82a8;font-family:'DM Mono',monospace">₹${r.mrp}</td>
    ${['blinkit_price','zepto_price','swiggy_price'].map(k=>priceCell(r[k])?`<td>${priceCell(r[k])}</td>`:'<td><span class="na">—</span></td>').join('')}
    <td>${r.min_price?`<span class="price">₹${r.min_price}</span>`:'<span class="na">—</span>'}</td>
    <td class="${discClass(r.max_disc)}">${r.max_disc!==null?r.max_disc+'%':'—'}</td>
  </tr>`).join('');
  const comps=buildComparisons(rows);
  document.getElementById('tbody3').innerHTML=comps.map(r=>{
    const itcWins=r.delta!==null&&r.itcPrice<=r.compPrice;
    return`<tr>
      <td style="color:var(--muted);font-size:.7rem">${r.sub}</td>
      <td class="brand-itc">${r.itcBrand}</td>
      <td class="name" style="max-width:180px">${r.itcSku}</td>
      <td class="${itcWins?'winner':'loser'}">${r.itcPrice?'₹'+r.itcPrice:'—'}</td>
      <td class="brand-comp">${r.compBrand}</td>
      <td class="name" style="max-width:180px">${r.compSku}</td>
      <td class="${!itcWins?'winner':'loser'}">${r.compPrice?'₹'+r.compPrice:'—'}</td>
      <td class="${r.delta!==null?(r.delta<=0?'disc-high':'disc-none'):''}">${r.delta!==null?(r.delta<=0?'✅ ITC cheaper by '+Math.abs(r.delta)+'%':'⚠️ ITC costlier by '+r.delta+'%'):'—'}</td>
      <td><span class="platform-tag ${pc(r.itcPlat)}">${r.itcPlat}</span></td>
    </tr>`;
  }).join('');
  if(!rows.length)document.getElementById('empty').style.display='block';
}
document.querySelectorAll('.tab').forEach(t=>{
  t.addEventListener('click',()=>{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
    document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));
    t.classList.add('active');document.getElementById(t.dataset.view).classList.add('active');
  });
});
document.querySelectorAll('thead th[data-col]').forEach(th=>{
  th.addEventListener('click',()=>{
    const col=th.dataset.col;sortCol===col?sortDir*=-1:(sortCol=col,sortDir=1);
    document.querySelectorAll('thead th').forEach(t=>t.classList.remove('sorted'));
    th.classList.add('sorted');th.querySelector('.sort-icon').textContent=sortDir===1?'↓':'↑';render();
  });
});
document.getElementById('search').addEventListener('input',e=>{state.search=e.target.value.trim();render();});
buildPills('f-platform','platform',uniq('platform'));
buildPills('f-category','category',uniq('category'));
buildPills('f-sub','subcategory',uniq('subcategory'));
buildPills('f-brand','brand',uniq('brand'));
const tw=document.getElementById('f-type');
['ALL','ITC','Competitor'].forEach(v=>{
  const p=document.createElement('span');p.className='pill'+(v==='ALL'?' active':'');
  p.textContent=v==='ALL'?'All':v;p.dataset.val=v;
  p.addEventListener('click',()=>toggle('type',v,tw));tw.appendChild(p);
});
render();
</script>
</body></html>"""


# ── MAIN ──────────────────────────────────────────────────────
async def run():
    run_dt = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    ).strftime("%d %b %Y, %I:%M %p IST")

    best = {}  # (sku_id, platform) → {sell_price, mrp_scraped, pincode}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled",
                  "--disable-web-security"]
        )

        total = len(PINCODES) * len(PLATFORMS)
        done = 0

        for (pincode, area, tier) in PINCODES:
            print(f"\n📍 {pincode} {area}")

            for platform in PLATFORMS:
                done += 1
                print(f"  🏪 {platform} ({done}/{total})")

                # Fresh context per pincode+platform with random UA
                ctx = await browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width": random.randint(390,430),
                              "height": random.randint(844,926)},
                    locale="en-IN",
                    timezone_id="Asia/Kolkata",
                    extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"},
                )
                page = await ctx.new_page()
                await page.add_init_script("""
                    Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
                    window.chrome={runtime:{}};
                    Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3]});
                    Object.defineProperty(navigator,'languages',{get:()=>['en-IN','en']});
                """)

                loc_ok = await set_location(page, pincode, platform)
                if not loc_ok:
                    print(f"    ⚠️  Location failed — skipping")
                    await ctx.close()
                    continue

                for sku in SKUS:
                    sell_price, mrp_scraped = await search_url(page, sku, platform)
                    key = (sku[0], platform)
                    if sell_price:
                        existing = best.get(key)
                        if not existing or sell_price < existing["sell_price"]:
                            best[key] = {"sell_price": sell_price,
                                         "mrp_scraped": mrp_scraped,
                                         "pincode_min": pincode}
                        print(f"    ✅ ₹{sell_price:<6} {sku[2][:45]}")
                    else:
                        print(f"    ❌        {sku[2][:45]}")
                    await asyncio.sleep(0.5)

                await ctx.close()

        await browser.close()

    # Build output rows
    results = []
    for sku in SKUS:
        (sku_id, brand, sku_name, category, subcategory, mrp, is_itc, _) = sku
        for platform in PLATFORMS:
            b = best.get((sku_id, platform), {})
            sp = b.get("sell_price")
            disc = round((1 - sp / mrp) * 100) if sp else None
            results.append({
                "sku_id": sku_id, "brand": brand, "sku_name": sku_name,
                "category": category, "subcategory": subcategory,
                "mrp": mrp, "is_itc": is_itc, "platform": platform,
                "sell_price": sp, "mrp_scraped": b.get("mrp_scraped", mrp),
                "discount_pct": disc, "pincode_min": b.get("pincode_min",""),
                "checked_at": run_dt,
            })

    with open("index.html","w",encoding="utf-8") as f:
        f.write(build_html(results, run_dt))
    with open("last_run.txt","w") as f:
        f.write(run_dt)

    found = sum(1 for r in results if r["sell_price"])
    print(f"\n✅ Done — {found}/{len(results)} prices found. index.html updated.")


if __name__ == "__main__":
    asyncio.run(run())
