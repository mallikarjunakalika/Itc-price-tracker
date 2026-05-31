"""
ITC Foods & Personal Care — Q-Commerce Price Tracker
=====================================================
Tracks ITC + competitor SKU prices across Blinkit, Zepto, Swiggy Instamart
for 29 ECAL pincodes. Reports LOWEST price to consumer across all pincodes.

Outputs: index.html — interactive dashboard with 3 views:
  1. Price Tracker     — lowest price per SKU per platform
  2. Discount Analysis — selling price vs MRP
  3. ITC vs Competitor — side-by-side brand comparison
"""

import asyncio, re, json, datetime
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
# (sku_id, brand, search_name, category, subcategory, mrp, is_itc)
SKUS = [
    # ── ITC FOODS ──────────────────────────────────────────────
    # Sunfeast
    ("SF_DF_75",    "Sunfeast", "Sunfeast Dark Fantasy Choco Fills 75g",       "Foods", "Biscuits",   30,  True),
    ("SF_DF_300",   "Sunfeast", "Sunfeast Dark Fantasy Choco Fills 300g",      "Foods", "Biscuits",  110,  True),
    ("SF_MM_150",   "Sunfeast", "Sunfeast Mom's Magic Butter 150g",            "Foods", "Biscuits",   30,  True),
    ("SF_FL_150",   "Sunfeast", "Sunfeast Farmlite Digestive 150g",            "Foods", "Biscuits",   35,  True),
    ("SF_ML_250",   "Sunfeast", "Sunfeast Marie Light 250g",                   "Foods", "Biscuits",   25,  True),
    # Bingo
    ("BG_MA_65",    "Bingo",    "Bingo Mad Angles Achaari Masti 65g",          "Foods", "Snacks",     20,  True),
    ("BG_TM_65",    "Bingo",    "Bingo Tedhe Medhe Masala 65g",                "Foods", "Snacks",     20,  True),
    ("BG_OS_52",    "Bingo",    "Bingo Original Style Cream Onion 52g",        "Foods", "Snacks",     20,  True),
    ("BG_RS_90",    "Bingo",    "Bingo Ridge Spiced 90g",                      "Foods", "Snacks",     30,  True),
    # Yippee
    ("YP_MM_4P",    "Yippee",   "Yippee Magic Masala Noodles 70g pack of 4",   "Foods", "Noodles",    60,  True),
    ("YP_CM_4P",    "Yippee",   "Yippee Classic Masala Noodles 70g pack of 4", "Foods", "Noodles",    60,  True),
    # Aashirvaad
    ("AA_AT_5K",    "Aashirvaad","Aashirvaad Whole Wheat Atta 5kg",            "Foods", "Staples",   280,  True),
    ("AA_AT_10K",   "Aashirvaad","Aashirvaad Whole Wheat Atta 10kg",           "Foods", "Staples",   520,  True),
    ("AA_SL_1K",    "Aashirvaad","Aashirvaad Salt 1kg",                        "Foods", "Staples",    20,  True),
    ("AA_IM_BC",    "Aashirvaad","Aashirvaad Instant Mix Butter Chicken",       "Foods", "Staples",    85,  True),
    # B Natural
    ("BN_MF_1L",    "B Natural", "B Natural Mixed Fruit Juice 1L",             "Foods", "Beverages", 120,  True),
    ("BN_OR_1L",    "B Natural", "B Natural Orange Juice 1L",                  "Foods", "Beverages", 120,  True),
    # Kitchens of India
    ("KI_BC_285",   "Kitchens of India","Kitchens of India Butter Chicken 285g","Foods","Ready to Eat",180, True),
    ("KI_DC_285",   "Kitchens of India","Kitchens of India Dal Chicken 285g",  "Foods", "Ready to Eat",180, True),

    # ── ITC PERSONAL CARE ──────────────────────────────────────
    # Fiama
    ("FM_SG_BC",    "Fiama",    "Fiama Shower Gel Blackcurrant 250ml",         "Personal Care", "Bath",     299, True),
    ("FM_SG_PH",    "Fiama",    "Fiama Shower Gel Peach 250ml",                "Personal Care", "Bath",     299, True),
    ("FM_SH_DR",    "Fiama",    "Fiama Shampoo Damage Repair 340ml",           "Personal Care", "Hair",     349, True),
    ("FM_SH_VB",    "Fiama",    "Fiama Shampoo Volume Boost 340ml",            "Personal Care", "Hair",     349, True),
    ("FM_FW_100",   "Fiama",    "Fiama Face Wash Brightening 100ml",           "Personal Care", "Skin",     199, True),
    ("FM_BB_3P",    "Fiama",    "Fiama Bathing Bar pack of 3",                 "Personal Care", "Bath",     165, True),
    # Engage
    ("EN_SP_150",   "Engage",   "Engage Spell Deodorant Men 150ml",            "Personal Care", "Deo",      230, True),
    ("EN_TS_150",   "Engage",   "Engage Tease Deodorant Women 150ml",          "Personal Care", "Deo",      230, True),
    ("EN_PP_M",     "Engage",   "Engage Pocket Perfume Men 18ml",              "Personal Care", "Deo",      175, True),
    ("EN_PP_W",     "Engage",   "Engage Pocket Perfume Women 18ml",            "Personal Care", "Deo",      175, True),
    # Vivel
    ("VV_SP_4P",    "Vivel",    "Vivel Active Fair Soap 100g pack of 4",       "Personal Care", "Bath",     148, True),
    ("VV_SH_340",   "Vivel",    "Vivel Shampoo Silky Smooth 340ml",            "Personal Care", "Hair",     249, True),
    # Savlon
    ("SV_HW_200",   "Savlon",   "Savlon Moisturising Hand Wash 200ml",         "Personal Care", "Hygiene",  109, True),
    ("SV_AL_500",   "Savlon",   "Savlon Antiseptic Liquid 500ml",              "Personal Care", "Hygiene",  199, True),
    # Nimyle
    ("NM_FC_1L",    "Nimyle",   "Nimyle Neem Floor Cleaner 1L",                "Personal Care", "Home",     120, True),
    ("NM_FC_2L",    "Nimyle",   "Nimyle Neem Floor Cleaner 2L",                "Personal Care", "Home",     210, True),

    # ── COMPETITORS — FOODS ────────────────────────────────────
    ("BR_GD_200",   "Britannia","Britannia Good Day Butter Cookies 200g",      "Foods", "Biscuits",   35, False),
    ("BR_NC_250",   "Britannia","Britannia NutriChoice Digestive 250g",        "Foods", "Biscuits",   40, False),
    ("PR_PG_250",   "Parle",    "Parle G Original Glucose Biscuits 250g",      "Foods", "Biscuits",   20, False),
    ("NS_MG_4P",    "Maggi",    "Maggi 2 Minute Noodles Masala 70g pack of 4", "Foods", "Noodles",    60, False),
    ("PG_LY_52",    "Lays",     "Lays Classic Salted Chips 52g",               "Foods", "Snacks",     20, False),
    ("PG_KU_65",    "Kurkure",  "Kurkure Masala Munch 65g",                    "Foods", "Snacks",     20, False),
    ("PN_AT_5K",    "Patanjali","Patanjali Whole Wheat Atta 5kg",              "Foods", "Staples",   220, False),
    ("RL_MF_1L",    "Real",     "Real Mixed Fruit Juice 1L",                   "Foods", "Beverages", 120, False),

    # ── COMPETITORS — PERSONAL CARE ───────────────────────────
    ("DV_BW_250",   "Dove",     "Dove Deeply Nourishing Body Wash 250ml",      "Personal Care", "Bath",     299, False),
    ("LB_HW_200",   "Lifebuoy", "Lifebuoy Total Hand Wash 200ml",              "Personal Care", "Hygiene",  109, False),
    ("PT_SH_340",   "Pantene",  "Pantene Anti Dandruff Shampoo 340ml",         "Personal Care", "Hair",     349, False),
    ("DT_HW_200",   "Dettol",   "Dettol Original Hand Wash 200ml",             "Personal Care", "Hygiene",  109, False),
    ("VS_BL_200",   "Vaseline", "Vaseline Intensive Care Body Lotion 200ml",   "Personal Care", "Skin",     199, False),
    ("HH_SH_340",   "Head & Shoulders","Head and Shoulders Anti Dandruff Shampoo 340ml","Personal Care","Hair",349,False),
    ("OL_FW_100",   "Olay",     "Olay Natural White Face Wash 100ml",          "Personal Care", "Skin",     299, False),
]

PLATFORMS = ["Blinkit", "Zepto", "Swiggy Instamart"]


# ── HELPERS ────────────────────────────────────────────────────
def extract_prices(text):
    """Return all ₹ amounts found in text as list of ints."""
    return [int(m) for m in re.findall(r'₹\s*(\d+)', text)]

def product_match(search_name, card_text):
    """Fuzzy match: key words of search name appear in card text."""
    card_lower = card_text.lower()
    # Remove pack sizes for core matching
    core = re.sub(r'\b(\d+g|\d+ml|\d+kg|\d+l|pack of \d+|\d+s)\b', '', search_name.lower())
    words = [w for w in core.split() if len(w) > 2]
    return sum(1 for w in words if w in card_lower) >= max(2, len(words) * 0.6)


async def set_location(page, pincode, platform):
    urls = {
        "Blinkit":          "https://blinkit.com",
        "Zepto":            "https://www.zeptonow.com",
        "Swiggy Instamart": "https://www.swiggy.com/instamart",
    }
    try:
        await page.goto(urls[platform], timeout=35000)
        await page.wait_for_timeout(3000)
        for sel in ["[data-testid='location-bar']", "text=Detect Location",
                    "[class*='location']", "text=Enter Location", "text=Enter manually"]:
            try:
                await page.click(sel, timeout=2500)
                await page.wait_for_timeout(1000)
                break
            except Exception:
                pass
        for sel in ["input[placeholder*='pincode']","input[placeholder*='Pincode']",
                    "input[placeholder*='Enter']","input[placeholder*='area']",
                    "input[placeholder*='Search']","input[type='text']"]:
            try:
                inp = page.locator(sel).first
                await inp.fill(pincode, timeout=4000)
                await page.wait_for_timeout(1500)
                for sug in ["[data-testid*='suggestion']","[data-testid*='location']",
                            "[class*='suggestion']","[class*='location-item']",
                            "[role='option']","li"]:
                    try:
                        await page.locator(sug).first.click(timeout=2500)
                        await page.wait_for_timeout(2000)
                        return True
                    except Exception:
                        pass
            except Exception:
                pass
        return False
    except Exception:
        return False


async def search_and_extract(page, sku, platform):
    """
    Search for SKU, return (selling_price, mrp) or (None, None).
    Returns the best-matching product's prices.
    """
    sku_id, brand, search_name, category, subcategory, mrp_expected, is_itc = sku
    try:
        search_inp = page.locator(
            "input[placeholder*='Search'], input[type='search']"
        ).first
        await search_inp.click(timeout=5000)
        await search_inp.fill("", timeout=2000)
        await search_inp.type(search_name[:30], delay=70)  # first 30 chars enough
        await page.wait_for_timeout(3000)

        card_sels = {
            "Blinkit":          ".product-card, [data-testid='product-item'], [class*='ProductCard']",
            "Zepto":            "[class*='ProductCard'], [class*='product-card']",
            "Swiggy Instamart": "[class*='ItemCard'], [class*='item-card'], [class*='Product']",
        }

        cards = page.locator(card_sels.get(platform, "[class*='card']"))
        count = await cards.count()

        for i in range(min(count, 20)):
            try:
                card = cards.nth(i)
                card_text = await card.inner_text(timeout=1000)

                if not product_match(search_name, card_text):
                    continue

                prices = extract_prices(card_text)
                if not prices:
                    continue

                # Selling price = min price found, MRP = max price found
                sell_price = min(prices)
                mrp_scraped = max(prices) if len(prices) > 1 else None

                # Sanity check — price should be reasonable vs expected MRP
                if sell_price > mrp_expected * 2:
                    continue

                return sell_price, mrp_scraped or mrp_expected

            except Exception:
                continue

    except Exception:
        pass

    return None, None


# ── HTML BUILDER ───────────────────────────────────────────────
def build_html(results, run_dt):
    """
    results: list of dicts with fields:
      sku_id, brand, sku_name, category, subcategory, mrp,
      is_itc, platform, sell_price, mrp_scraped, discount_pct,
      pincode_min, checked_at
    """
    data_str = json.dumps(results)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ITC Price Tracker · Q-Commerce</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{{--bg:#080d1a;--surface:#0e1628;--border:#1e2d4a;--gold:#c9a84c;--gold2:#e8c97a;
         --text:#dce8ff;--muted:#6b82a8;--green:#22c55e;--red:#ef4444;--blue:#60a5fa;--purple:#a78bfa}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:'Syne',sans-serif;min-height:100vh}}

  /* HEADER */
  header{{border-bottom:1px solid var(--border);padding:18px 28px;display:flex;align-items:center;justify-content:space-between;background:linear-gradient(90deg,#080d1a 60%,#0f1c35)}}
  .logo{{display:flex;align-items:center;gap:12px}}
  .logo-mark{{width:36px;height:36px;border-radius:8px;background:linear-gradient(135deg,#c9a84c,#7a5a1a);display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:800;color:#fff}}
  h1{{font-size:1.1rem;font-weight:700}}
  .subtitle{{font-size:.72rem;color:var(--muted);margin-top:2px;font-family:'DM Mono',monospace}}
  .run-time{{font-size:.68rem;color:var(--muted);font-family:'DM Mono',monospace;text-align:right}}
  .run-time span{{color:var(--gold);font-weight:600}}

  /* STATS */
  .stats{{display:flex;gap:1px;border-bottom:1px solid var(--border);background:var(--border)}}
  .stat{{flex:1;background:var(--surface);padding:12px 18px}}
  .stat-val{{font-size:1.5rem;font-weight:800;color:var(--gold);line-height:1}}
  .stat-lbl{{font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:2px}}

  /* TABS */
  .tabs{{display:flex;border-bottom:2px solid var(--border);background:var(--surface);padding:0 28px}}
  .tab{{padding:12px 20px;font-size:.8rem;font-weight:700;cursor:pointer;color:var(--muted);border-bottom:2px solid transparent;margin-bottom:-2px;transition:all .15s;letter-spacing:.5px}}
  .tab.active{{color:var(--gold);border-bottom-color:var(--gold)}}
  .tab:hover:not(.active){{color:var(--text)}}

  /* FILTERS */
  .filters{{padding:14px 28px;border-bottom:1px solid var(--border);display:flex;flex-wrap:wrap;gap:14px;align-items:flex-start;background:var(--surface)}}
  .filter-group{{display:flex;flex-direction:column;gap:5px}}
  .filter-label{{font-size:.58rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted)}}
  .pills{{display:flex;flex-wrap:wrap;gap:4px}}
  .pill{{padding:3px 10px;border-radius:20px;font-size:.7rem;font-weight:600;cursor:pointer;border:1px solid var(--border);background:#12213a;color:var(--muted);transition:all .15s;user-select:none}}
  .pill.active{{background:var(--gold);color:#080d1a;border-color:var(--gold)}}
  .pill:hover:not(.active){{border-color:var(--gold);color:var(--text)}}
  .search-wrap{{margin-left:auto;display:flex;align-items:flex-end;gap:8px}}
  #search{{background:var(--bg);border:1px solid var(--border);color:var(--text);padding:5px 11px;border-radius:8px;font-family:'Syne',sans-serif;font-size:.78rem;width:180px;outline:none}}
  #search:focus{{border-color:var(--gold)}}
  #count-badge{{font-size:.68rem;color:var(--muted);font-family:'DM Mono',monospace;padding-bottom:7px}}

  /* TABLE */
  .table-wrap{{overflow-x:auto;padding-bottom:40px}}
  .view{{display:none}}.view.active{{display:block}}
  table{{width:100%;border-collapse:collapse;font-size:.76rem}}
  thead th{{position:sticky;top:0;z-index:10;background:#0b1223;border-bottom:2px solid var(--gold);padding:9px 13px;text-align:left;font-size:.58rem;text-transform:uppercase;letter-spacing:1.2px;color:var(--gold);white-space:nowrap;cursor:pointer}}
  thead th:hover{{color:var(--gold2)}}
  .sort-icon{{opacity:.35;margin-left:3px}}
  thead th.sorted .sort-icon{{opacity:1}}
  tbody tr{{border-bottom:1px solid var(--border);transition:background .1s}}
  tbody tr:hover{{background:#0f1e38}}
  td{{padding:7px 13px;white-space:nowrap}}
  td.name{{white-space:normal;max-width:220px;font-weight:500}}
  td.brand-itc{{color:var(--gold2);font-weight:700}}
  td.brand-comp{{color:var(--blue);font-weight:600}}
  .platform-tag{{font-size:.6rem;font-weight:700;padding:2px 7px;border-radius:4px;text-transform:uppercase}}
  .plat-blinkit{{background:#1a2e0a;color:#86efac}}
  .plat-zepto{{background:#2a1040;color:#c4b5fd}}
  .plat-swiggy{{background:#2a1010;color:#fca5a5}}
  .price{{font-family:'DM Mono',monospace;font-weight:700;color:var(--green)}}
  .mrp{{font-family:'DM Mono',monospace;font-size:.68rem;color:#4b5e7a;text-decoration:line-through}}
  .disc-high{{color:var(--green);font-weight:700}}
  .disc-mid{{color:var(--gold);font-weight:600}}
  .disc-low{{color:var(--muted)}}
  .disc-none{{color:#374151}}
  .badge-itc{{background:#1a2e0a;color:#86efac;font-size:.58rem;padding:1px 7px;border-radius:10px;font-weight:700}}
  .badge-comp{{background:#12213a;color:var(--blue);font-size:.58rem;padding:1px 7px;border-radius:10px;font-weight:600}}
  .na{{color:#2d3f5a;font-family:'DM Mono',monospace;font-size:.68rem}}
  #empty{{text-align:center;padding:50px;color:var(--muted);display:none}}

  /* COMPARISON TABLE (View 3) */
  .comp-table td.winner{{background:#0d2010;color:var(--green);font-weight:700}}
  .comp-table td.loser{{color:#4b5e7a}}
</style>
</head>
<body>

<header>
  <div class="logo">
    <div class="logo-mark">₹</div>
    <div><h1>ITC Q-Commerce Price Tracker</h1>
    <div class="subtitle">Foods & Personal Care · ECAL Branch · 29 Zones</div></div>
  </div>
  <div class="run-time">Updated<br><span>{run_dt}</span></div>
</header>

<div class="stats">
  <div class="stat"><div class="stat-val" id="s-skus">—</div><div class="stat-lbl">SKUs Tracked</div></div>
  <div class="stat"><div class="stat-val" id="s-found">—</div><div class="stat-lbl">Found on Platforms</div></div>
  <div class="stat"><div class="stat-val" id="s-disc">—</div><div class="stat-lbl">Avg ITC Discount %</div></div>
  <div class="stat"><div class="stat-val" id="s-cheap">—</div><div class="stat-lbl">Cheapest Platform</div></div>
  <div class="stat"><div class="stat-val" id="s-itc-vs">—</div><div class="stat-lbl">ITC vs Competitor Δ%</div></div>
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

  <!-- VIEW 1: Price Tracker -->
  <div class="view active" id="v1">
    <table>
      <thead><tr>
        <th data-col="brand">Brand <span class="sort-icon">↕</span></th>
        <th data-col="sku_name">Product <span class="sort-icon">↕</span></th>
        <th data-col="category">Category <span class="sort-icon">↕</span></th>
        <th data-col="subcategory">Sub-cat <span class="sort-icon">↕</span></th>
        <th data-col="platform">Platform <span class="sort-icon">↕</span></th>
        <th data-col="sell_price">Best Price ↓ <span class="sort-icon">↕</span></th>
        <th data-col="mrp">MRP <span class="sort-icon">↕</span></th>
        <th data-col="discount_pct">Disc % <span class="sort-icon">↕</span></th>
        <th data-col="is_itc">Type <span class="sort-icon">↕</span></th>
      </tr></thead>
      <tbody id="tbody1"></tbody>
    </table>
  </div>

  <!-- VIEW 2: Discount Analysis -->
  <div class="view" id="v2">
    <table>
      <thead><tr>
        <th data-col="brand">Brand <span class="sort-icon">↕</span></th>
        <th data-col="sku_name">Product <span class="sort-icon">↕</span></th>
        <th data-col="mrp">MRP <span class="sort-icon">↕</span></th>
        <th data-col="blinkit_price">Blinkit <span class="sort-icon">↕</span></th>
        <th data-col="zepto_price">Zepto <span class="sort-icon">↕</span></th>
        <th data-col="swiggy_price">Swiggy <span class="sort-icon">↕</span></th>
        <th data-col="min_price">Lowest <span class="sort-icon">↕</span></th>
        <th data-col="max_disc">Max Disc% <span class="sort-icon">↕</span></th>
      </tr></thead>
      <tbody id="tbody2"></tbody>
    </table>
  </div>

  <!-- VIEW 3: ITC vs Competitor -->
  <div class="view" id="v3">
    <table class="comp-table">
      <thead><tr>
        <th>Sub-category</th>
        <th>ITC Brand</th>
        <th>ITC Product</th>
        <th>ITC Best Price</th>
        <th>Competitor Brand</th>
        <th>Competitor Product</th>
        <th>Comp Best Price</th>
        <th>ITC vs Comp</th>
        <th>Platform</th>
      </tr></thead>
      <tbody id="tbody3"></tbody>
    </table>
  </div>

  <div id="empty">No results match your filters</div>
</div>

<script>
const RAW = {data_str};

// ── State ──────────────────────────────────────────────────
const state = {{
  platform: new Set(['ALL']), category: new Set(['ALL']),
  sub: new Set(['ALL']),      type: new Set(['ALL']),
  brand: new Set(['ALL']),    search: '',
}};
let activeView = 'v1', sortCol = null, sortDir = 1;

const uniq = k => [...new Set(RAW.map(r => r[k]).filter(Boolean))].sort();

function buildPills(id, key, vals) {{
  const w = document.getElementById(id);
  ['ALL', ...vals].forEach(v => {{
    const p = document.createElement('span');
    p.className = 'pill' + (v === 'ALL' ? ' active' : '');
    p.textContent = v === 'ALL' ? 'All' : v; p.dataset.val = v;
    p.addEventListener('click', () => toggle(key, v, w));
    w.appendChild(p);
  }});
}}

function toggle(key, val, wrap) {{
  const s = state[key];
  if (val === 'ALL') {{ s.clear(); s.add('ALL'); }}
  else {{ s.delete('ALL'); s.has(val) ? s.delete(val) : s.add(val); if (!s.size) s.add('ALL'); }}
  wrap.querySelectorAll('.pill').forEach(p => p.classList.toggle('active', s.has(p.dataset.val)));
  render();
}}

function filteredRaw() {{
  return RAW.filter(r => {{
    if (!state.platform.has('ALL') && !state.platform.has(r.platform)) return false;
    if (!state.category.has('ALL') && !state.category.has(r.category)) return false;
    if (!state.sub.has('ALL') && !state.sub.has(r.subcategory)) return false;
    if (!state.type.has('ALL')) {{
      if (state.type.has('ITC') && !r.is_itc) return false;
      if (state.type.has('Competitor') && r.is_itc) return false;
    }}
    if (!state.brand.has('ALL') && !state.brand.has(r.brand)) return false;
    if (state.search) {{
      const q = state.search.toLowerCase();
      if (!(r.sku_name||'').toLowerCase().includes(q) && !(r.brand||'').toLowerCase().includes(q)) return false;
    }}
    return true;
  }});
}}

// ── Pivot for View 2 ───────────────────────────────────────
function buildPivot(rows) {{
  const map = {{}};
  rows.forEach(r => {{
    if (!r.sell_price) return;
    const k = r.sku_id;
    if (!map[k]) map[k] = {{ sku_id:r.sku_id, brand:r.brand, sku_name:r.sku_name,
      category:r.category, subcategory:r.subcategory, mrp:r.mrp, is_itc:r.is_itc,
      blinkit_price:null, zepto_price:null, swiggy_price:null }};
    if (r.platform === 'Blinkit')          map[k].blinkit_price = r.sell_price;
    if (r.platform === 'Zepto')            map[k].zepto_price   = r.sell_price;
    if (r.platform === 'Swiggy Instamart') map[k].swiggy_price  = r.sell_price;
  }});
  return Object.values(map).map(r => {{
    const prices = [r.blinkit_price, r.zepto_price, r.swiggy_price].filter(Boolean);
    r.min_price = prices.length ? Math.min(...prices) : null;
    r.max_disc  = r.min_price ? Math.round((1 - r.min_price / r.mrp) * 100) : null;
    return r;
  }});
}}

// ── Comparison pairs for View 3 ────────────────────────────
const COMP_PAIRS = [
  ['Biscuits',    'Sunfeast',  'Britannia'],
  ['Biscuits',    'Sunfeast',  'Parle'],
  ['Snacks',      'Bingo',     'Lays'],
  ['Snacks',      'Bingo',     'Kurkure'],
  ['Noodles',     'Yippee',    'Maggi'],
  ['Staples',     'Aashirvaad','Patanjali'],
  ['Beverages',   'B Natural', 'Real'],
  ['Bath',        'Fiama',     'Dove'],
  ['Hair',        'Fiama',     'Pantene'],
  ['Hair',        'Fiama',     'Head & Shoulders'],
  ['Hygiene',     'Savlon',    'Lifebuoy'],
  ['Hygiene',     'Savlon',    'Dettol'],
  ['Skin',        'Fiama',     'Olay'],
  ['Deo',         'Engage',    'Vaseline'],
];

function buildComparisons(rows) {{
  const result = [];
  COMP_PAIRS.forEach(([sub, itcBrand, compBrand]) => {{
    const itcRows  = rows.filter(r => r.is_itc  && r.brand === itcBrand  && r.subcategory === sub && r.sell_price);
    const compRows = rows.filter(r => !r.is_itc && r.brand === compBrand && r.subcategory === sub && r.sell_price);
    if (!itcRows.length || !compRows.length) return;

    // Best price per SKU
    const itcBest  = itcRows.reduce((a,b)  => (a.sell_price <= b.sell_price ? a : b));
    const compBest = compRows.reduce((a,b) => (a.sell_price <= b.sell_price ? a : b));
    const delta = compBest.sell_price
      ? Math.round((itcBest.sell_price - compBest.sell_price) / compBest.sell_price * 100)
      : null;
    result.push({{ sub, itcBrand, itcSku: itcBest.sku_name, itcPrice: itcBest.sell_price,
      itcPlat: itcBest.platform, compBrand, compSku: compBest.sku_name,
      compPrice: compBest.sell_price, compPlat: compBest.platform, delta }});
  }});
  return result;
}}

// ── Render ─────────────────────────────────────────────────
function discClass(d) {{
  if (d === null) return 'disc-none';
  if (d >= 15) return 'disc-high';
  if (d >= 5)  return 'disc-mid';
  return 'disc-low';
}}
function pc(p) {{
  return p === 'Blinkit' ? 'plat-blinkit' : p === 'Zepto' ? 'plat-zepto' : 'plat-swiggy';
}}
function priceCell(p) {{
  return p ? `<span class="price">₹${{p}}</span>` : '<span class="na">—</span>';
}}

function updateStats(rows) {{
  const skus = new Set(rows.map(r => r.sku_id)).size;
  const found = rows.filter(r => r.sell_price).length;
  const itcRows = rows.filter(r => r.is_itc && r.sell_price && r.discount_pct !== null);
  const avgDisc = itcRows.length ? Math.round(itcRows.reduce((a,b) => a + b.discount_pct, 0) / itcRows.length) : 0;

  // Cheapest platform
  const platSums = {{}};
  rows.filter(r => r.sell_price).forEach(r => {{
    platSums[r.platform] = (platSums[r.platform]||0) + r.sell_price;
  }});
  const cheapPlat = Object.entries(platSums).sort((a,b)=>a[1]-b[1])[0];

  // ITC vs competitor avg price delta
  const itcAvg  = rows.filter(r => r.is_itc  && r.sell_price).reduce((a,b,_,arr)=>a+b.sell_price/arr.length,0);
  const compAvg = rows.filter(r => !r.is_itc && r.sell_price).reduce((a,b,_,arr)=>a+b.sell_price/arr.length,0);
  const delta = compAvg ? Math.round((itcAvg - compAvg) / compAvg * 100) : 0;

  document.getElementById('s-skus').textContent   = skus;
  document.getElementById('s-found').textContent  = found;
  document.getElementById('s-disc').textContent   = avgDisc + '%';
  document.getElementById('s-cheap').textContent  = cheapPlat ? cheapPlat[0].split(' ')[0] : '—';
  document.getElementById('s-itc-vs').textContent = (delta >= 0 ? '+' : '') + delta + '%';
  document.getElementById('count-badge').textContent = rows.length + ' rows';
}}

function render() {{
  const rows = filteredRaw().sort((a,b) => {{
    if (!sortCol) return 0;
    const va = a[sortCol] ?? '', vb = b[sortCol] ?? '';
    return va < vb ? -sortDir : va > vb ? sortDir : 0;
  }});

  updateStats(rows);
  document.getElementById('empty').style.display = 'none';

  // View 1
  document.getElementById('tbody1').innerHTML = rows.map(r => `<tr>
    <td class="${{r.is_itc ? 'brand-itc' : 'brand-comp'}}">${{r.brand}}</td>
    <td class="name">${{r.sku_name}}</td>
    <td>${{r.category}}</td>
    <td style="color:var(--muted);font-size:.7rem">${{r.subcategory}}</td>
    <td><span class="platform-tag ${{pc(r.platform)}}">${{r.platform}}</span></td>
    <td>${{r.sell_price ? `<span class="price">₹${{r.sell_price}}</span>` : '<span class="na">—</span>'}}</td>
    <td><span class="mrp">₹${{r.mrp}}</span></td>
    <td class="${{discClass(r.discount_pct)}}">${{r.discount_pct !== null ? r.discount_pct + '%' : '—'}}</td>
    <td>${{r.is_itc ? '<span class="badge-itc">ITC</span>' : '<span class="badge-comp">Competitor</span>'}}</td>
  </tr>`).join('');

  // View 2
  const pivot = buildPivot(rows);
  document.getElementById('tbody2').innerHTML = pivot.map(r => `<tr>
    <td class="${{r.is_itc ? 'brand-itc' : 'brand-comp'}}">${{r.brand}}</td>
    <td class="name">${{r.sku_name}}</td>
    <td><span class="mrp" style="text-decoration:none;color:#6b82a8">₹${{r.mrp}}</span></td>
    <td>${{priceCell(r.blinkit_price)}}</td>
    <td>${{priceCell(r.zepto_price)}}</td>
    <td>${{priceCell(r.swiggy_price)}}</td>
    <td>${{r.min_price ? `<span class="price" style="font-size:.85rem">₹${{r.min_price}}</span>` : '<span class="na">—</span>'}}</td>
    <td class="${{discClass(r.max_disc)}}">${{r.max_disc !== null ? r.max_disc + '%' : '—'}}</td>
  </tr>`).join('');

  // View 3
  const comps = buildComparisons(rows);
  document.getElementById('tbody3').innerHTML = comps.map(r => {{
    const itcWins = r.delta !== null && r.itcPrice <= r.compPrice;
    return `<tr>
      <td style="color:var(--muted);font-size:.7rem">${{r.sub}}</td>
      <td class="brand-itc">${{r.itcBrand}}</td>
      <td class="name" style="max-width:180px">${{r.itcSku}}</td>
      <td class="${{itcWins ? 'winner' : 'loser'}}">${{r.itcPrice ? '₹'+r.itcPrice : '—'}}</td>
      <td class="brand-comp">${{r.compBrand}}</td>
      <td class="name" style="max-width:180px">${{r.compSku}}</td>
      <td class="${{!itcWins ? 'winner' : 'loser'}}">${{r.compPrice ? '₹'+r.compPrice : '—'}}</td>
      <td class="${{r.delta !== null ? (r.delta <= 0 ? 'disc-high' : 'disc-none') : ''}}">
        ${{r.delta !== null ? (r.delta <= 0 ? '✅ ITC cheaper by ' + Math.abs(r.delta) + '%' : '⚠️ ITC costlier by ' + r.delta + '%') : '—'}}
      </td>
      <td><span class="platform-tag ${{pc(r.itcPlat)}}">${{r.itcPlat}}</span></td>
    </tr>`;
  }}).join('');

  if (!rows.length) document.getElementById('empty').style.display = 'block';
}}

// ── Tabs ───────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(t => {{
  t.addEventListener('click', () => {{
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.view').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    document.getElementById(t.dataset.view).classList.add('active');
    activeView = t.dataset.view;
  }});
}});

// ── Sort ───────────────────────────────────────────────────
document.querySelectorAll('thead th[data-col]').forEach(th => {{
  th.addEventListener('click', () => {{
    const col = th.dataset.col;
    sortCol === col ? sortDir *= -1 : (sortCol = col, sortDir = 1);
    document.querySelectorAll('thead th').forEach(t => t.classList.remove('sorted'));
    th.classList.add('sorted');
    th.querySelector('.sort-icon').textContent = sortDir === 1 ? '↓' : '↑';
    render();
  }});
}});

// ── Search ─────────────────────────────────────────────────
document.getElementById('search').addEventListener('input', e => {{
  state.search = e.target.value.trim(); render();
}});

// ── Init ───────────────────────────────────────────────────
buildPills('f-platform', 'platform', uniq('platform'));
buildPills('f-category', 'category', uniq('category'));
buildPills('f-sub',      'subcategory', uniq('subcategory'));
buildPills('f-brand',    'brand',    uniq('brand'));

const tw = document.getElementById('f-type');
['ALL','ITC','Competitor'].forEach(v => {{
  const p = document.createElement('span');
  p.className = 'pill' + (v === 'ALL' ? ' active' : '');
  p.textContent = v === 'ALL' ? 'All' : v; p.dataset.val = v;
  p.addEventListener('click', () => toggle('type', v, tw));
  tw.appendChild(p);
}});

render();
</script>
</body></html>"""


# ── MAIN ───────────────────────────────────────────────────────
async def run():
    run_dt = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    ).strftime("%d %b %Y, %I:%M %p IST")

    # Results keyed by (sku_id, platform) → best (lowest) price seen
    best = {}  # (sku_id, platform) → {sell_price, mrp_scraped, pincode}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"]
        )

        total = len(PINCODES) * len(PLATFORMS)
        done = 0

        for (pincode, area, tier) in PINCODES:
            print(f"\n📍 {pincode} {area}")

            for platform in PLATFORMS:
                done += 1
                print(f"  🏪 {platform} ({done}/{total})")

                page = await browser.new_page()
                await page.add_init_script(
                    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                )

                loc_ok = await set_location(page, pincode, platform)
                if not loc_ok:
                    print(f"    ⚠️  Location failed")
                    await page.close()
                    continue

                for sku in SKUS:
                    sku_id = sku[0]
                    sell_price, mrp_scraped = await search_and_extract(page, sku, platform)

                    key = (sku_id, platform)
                    if sell_price:
                        existing = best.get(key)
                        if not existing or sell_price < existing['sell_price']:
                            best[key] = {
                                'sell_price':  sell_price,
                                'mrp_scraped': mrp_scraped,
                                'pincode_min': pincode,
                            }
                        icon = f"✅ ₹{sell_price}"
                    else:
                        icon = "❌"

                    print(f"    {icon:<12} {sku[2][:45]}")
                    await asyncio.sleep(0.5)

                await page.close()

        await browser.close()

    # ── Build final rows ───────────────────────────────────────
    results = []
    for sku in SKUS:
        (sku_id, brand, sku_name, category, subcategory, mrp, is_itc) = sku
        for platform in PLATFORMS:
            key = (sku_id, platform)
            b = best.get(key, {})
            sell_price  = b.get('sell_price')
            mrp_scraped = b.get('mrp_scraped', mrp)
            pincode_min = b.get('pincode_min', '')
            disc = round((1 - sell_price / mrp) * 100) if sell_price else None
            results.append({
                "sku_id":      sku_id,
                "brand":       brand,
                "sku_name":    sku_name,
                "category":    category,
                "subcategory": subcategory,
                "mrp":         mrp,
                "is_itc":      is_itc,
                "platform":    platform,
                "sell_price":  sell_price,
                "mrp_scraped": mrp_scraped,
                "discount_pct":disc,
                "pincode_min": pincode_min,
                "checked_at":  run_dt,
            })

    html = build_html(results, run_dt)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open("last_run.txt", "w") as f:
        f.write(run_dt)

    print(f"\n✅ Done — {len(results)} data points. index.html updated.")


if __name__ == "__main__":
    asyncio.run(run())
