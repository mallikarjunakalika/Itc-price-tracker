"""
ITC Q-Commerce Price Tracker  v3.0
Categories : Aashirvaad Atta · Nimyle · Yippee · Fiama Shower Gel
             + key competitors for each
Pincodes   : 3 representative zones (prices don't vary within Kolkata)
Platforms  : Blinkit · Zepto · Swiggy Instamart
Runtime    : ~45 minutes
"""

import asyncio, re, json, datetime, random
from playwright.async_api import async_playwright

# ── 3 REPRESENTATIVE PINCODES ─────────────────────────────────
PINCODES = [
    ("700019", "Ballygunge",        "Premium"),
    ("700064", "Salt Lake Sec I-III","Upper Mid"),
    ("700033", "Tollygunge",        "Upper Mid"),
]

# ── SKUs — 4 categories + competitors ─────────────────────────
# (sku_id, brand, display_name, category, subcategory, mrp, is_itc, search_query)
SKUS = [
    # ── AASHIRVAAD ATTA ──────────────────────────────────────
    ("AA_AT_5K",  "Aashirvaad","Aashirvaad Whole Wheat Atta 5kg",  "Foods","Atta", 280,True, "aashirvaad atta 5kg"),
    ("AA_AT_10K", "Aashirvaad","Aashirvaad Whole Wheat Atta 10kg", "Foods","Atta", 520,True, "aashirvaad atta 10kg"),
    ("PN_AT_5K",  "Patanjali", "Patanjali Whole Wheat Atta 5kg",   "Foods","Atta", 220,False,"patanjali atta 5kg"),
    ("AB_AT_5K",  "Aashirvad", "Annapurna Atta 5kg",               "Foods","Atta", 265,False,"annapurna atta 5kg"),

    # ── NIMYLE FLOOR CLEANER ─────────────────────────────────
    ("NM_FC_1L",  "Nimyle",   "Nimyle Neem Floor Cleaner 1L",      "Personal Care","Floor Cleaner",120,True, "nimyle floor cleaner 1l"),
    ("NM_FC_2L",  "Nimyle",   "Nimyle Neem Floor Cleaner 2L",      "Personal Care","Floor Cleaner",210,True, "nimyle floor cleaner 2l"),
    ("LZ_FC_1L",  "Lizol",    "Lizol Disinfectant Floor Cleaner 1L","Personal Care","Floor Cleaner",185,False,"lizol floor cleaner 1l"),
    ("HG_FC_1L",  "Harpic",   "Harpic Power Plus Floor Cleaner 1L","Personal Care","Floor Cleaner",130,False,"harpic floor cleaner 1l"),

    # ── YIPPEE NOODLES ───────────────────────────────────────
    ("YP_MM_4P",  "Yippee",   "Yippee Magic Masala Noodles 4 Pack","Foods","Noodles",60,True, "yippee magic masala noodles 4 pack"),
    ("YP_CM_4P",  "Yippee",   "Yippee Classic Masala Noodles 4 Pack","Foods","Noodles",60,True,"yippee classic masala noodles"),
    ("NS_MG_4P",  "Maggi",    "Maggi 2 Minute Noodles Masala 4 Pack","Foods","Noodles",60,False,"maggi 2 minute noodles masala 4 pack"),
    ("NS_MG_12P", "Maggi",    "Maggi 2 Minute Noodles 12 Pack",    "Foods","Noodles",180,False,"maggi noodles 12 pack"),

    # ── FIAMA SHOWER GEL ─────────────────────────────────────
    ("FM_SG_BC",  "Fiama",    "Fiama Shower Gel Blackcurrant 250ml","Personal Care","Shower Gel",299,True,"fiama shower gel blackcurrant 250ml"),
    ("FM_SG_PH",  "Fiama",    "Fiama Shower Gel Peach 250ml",      "Personal Care","Shower Gel",299,True,"fiama shower gel peach 250ml"),
    ("FM_SG_GR",  "Fiama",    "Fiama Shower Gel Green Tea 250ml",  "Personal Care","Shower Gel",299,True,"fiama shower gel green tea 250ml"),
    ("DV_BW_250", "Dove",     "Dove Body Wash Deeply Nourishing 250ml","Personal Care","Shower Gel",299,False,"dove body wash deeply nourishing 250ml"),
    ("DV_BW_500", "Dove",     "Dove Body Wash 500ml",              "Personal Care","Shower Gel",499,False,"dove body wash 500ml"),
]

PLATFORMS = ["Blinkit", "Zepto", "Swiggy Instamart"]

SEARCH_URLS = {
    "Blinkit":          "https://blinkit.com/s/?q={q}",
    "Zepto":            "https://www.zeptonow.com/search?query={q}",
    "Swiggy Instamart": "https://www.swiggy.com/instamart/search?query={q}",
}
BASE_URLS = {
    "Blinkit":          "https://blinkit.com",
    "Zepto":            "https://www.zeptonow.com",
    "Swiggy Instamart": "https://www.swiggy.com/instamart",
}
USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
]


# ── HELPERS ───────────────────────────────────────────────────
def extract_prices(text):
    nums = []
    for pat in [r'₹\s*(\d+)', r'Rs\.?\s*(\d+)', r'MRP[:\s]+(\d+)']:
        for m in re.finditer(pat, text, re.IGNORECASE):
            try: nums.append(int(m.group(1)))
            except: pass
    return sorted(set(nums))

def is_match(query, card_text, mrp):
    low = card_text.lower()
    core = re.sub(r'\b(\d+g|\d+ml|\d+kg|\d+l|pack of \d+|\d+ pack|\d+s?)\b','',query.lower())
    words = [w for w in re.split(r'\W+', core) if len(w) > 2]
    if not words: return False
    ratio = sum(1 for w in words if w in low) / len(words)
    if ratio < 0.5: return False
    prices = extract_prices(card_text)
    return not prices or min(prices) <= mrp * 3


async def set_location(page, pincode, platform):
    try:
        await page.goto(BASE_URLS[platform], timeout=40000, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        for sel in ["[data-testid='location-bar']","[class*='LocationBar']",
                    "text=Detect Location","text=Enter Location","[class*='location']"]:
            try:
                if await page.locator(sel).first.is_visible(timeout=1500):
                    await page.locator(sel).first.click()
                    await page.wait_for_timeout(1200)
                    break
            except: pass
        for sel in ["input[placeholder*='pincode' i]","input[placeholder*='area' i]",
                    "input[placeholder*='enter' i]","input[type='search']","input[type='text']"]:
            try:
                inp = page.locator(sel).first
                if not await inp.is_visible(timeout=1500): continue
                await inp.click()
                await inp.fill("")
                await inp.type(pincode, delay=90)
                await page.wait_for_timeout(1800)
                for sug in ["[data-testid*='suggestion']","[class*='suggestion' i]",
                            "[role='option']","li[class*='item']","li"]:
                    try:
                        first = page.locator(sug).first
                        if await first.is_visible(timeout=1500):
                            await first.click()
                            await page.wait_for_timeout(2000)
                            return True
                    except: pass
            except: pass
        body = await page.inner_text("body")
        return "₹" in body or "add" in body.lower()
    except: return False


async def scrape_sku(page, sku, platform):
    sku_id, brand, name, cat, sub, mrp, is_itc, query = sku
    try:
        url = SEARCH_URLS[platform].format(q=query.replace(" ","+"))
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)
        body = await page.inner_text("body")
        if "₹" not in body: return None, None
        card_sel = {
            "Blinkit":          "[class*='ProductCard'],[class*='product-card'],.product-card",
            "Zepto":            "[class*='ProductCard'],[class*='product-card']",
            "Swiggy Instamart": "[class*='ItemCard'],[class*='item-card'],[class*='Product']",
        }.get(platform,"[class*='card']")
        cards = page.locator(card_sel)
        count = await cards.count()
        for i in range(min(count, 25)):
            try:
                ct = await cards.nth(i).inner_text(timeout=800)
                if not is_match(query, ct, mrp): continue
                prices = extract_prices(ct)
                if not prices: continue
                sp = min(p for p in prices if 5 < p <= mrp * 3)
                mr = max(prices) if len(prices) > 1 else None
                return sp, mr or mrp
            except: continue
    except: pass
    return None, None


# ── HTML ──────────────────────────────────────────────────────
def build_html(results, run_dt):
    data_str = json.dumps(results)
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>ITC Price Tracker</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--bg:#080d1a;--sf:#0e1628;--bd:#1e2d4a;--gold:#c9a84c;--g2:#e8c97a;--tx:#dce8ff;--mu:#6b82a8;--gn:#22c55e;--bl:#60a5fa}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font-family:'Syne',sans-serif}
header{border-bottom:1px solid var(--bd);padding:18px 28px;display:flex;align-items:center;justify-content:space-between;background:linear-gradient(90deg,#080d1a 60%,#0f1c35)}
.logo{display:flex;align-items:center;gap:12px}
.lm{width:36px;height:36px;border-radius:8px;background:linear-gradient(135deg,#c9a84c,#7a5a1a);display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:800;color:#fff}
h1{font-size:1.1rem;font-weight:700}.sub{font-size:.7rem;color:var(--mu);font-family:'DM Mono',monospace}
.rt{font-size:.68rem;color:var(--mu);font-family:'DM Mono',monospace;text-align:right}.rt span{color:var(--gold);font-weight:600}
.stats{display:flex;gap:1px;border-bottom:1px solid var(--bd);background:var(--bd)}
.stat{flex:1;background:var(--sf);padding:12px 18px}
.sv{font-size:1.5rem;font-weight:800;color:var(--gold);line-height:1}
.sl{font-size:.6rem;color:var(--mu);text-transform:uppercase;letter-spacing:1px;margin-top:2px}
.tabs{display:flex;border-bottom:2px solid var(--bd);background:var(--sf);padding:0 28px}
.tab{padding:12px 18px;font-size:.78rem;font-weight:700;cursor:pointer;color:var(--mu);border-bottom:2px solid transparent;margin-bottom:-2px;transition:all .15s}
.tab.active{color:var(--gold);border-bottom-color:var(--gold)}.tab:hover:not(.active){color:var(--tx)}
.filters{padding:14px 28px;border-bottom:1px solid var(--bd);display:flex;flex-wrap:wrap;gap:14px;align-items:flex-start;background:var(--sf)}
.fg{display:flex;flex-direction:column;gap:5px}
.fl{font-size:.58rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--mu)}
.pills{display:flex;flex-wrap:wrap;gap:4px}
.pill{padding:3px 10px;border-radius:20px;font-size:.7rem;font-weight:600;cursor:pointer;border:1px solid var(--bd);background:#12213a;color:var(--mu);transition:all .15s;user-select:none}
.pill.active{background:var(--gold);color:#080d1a;border-color:var(--gold)}.pill:hover:not(.active){border-color:var(--gold);color:var(--tx)}
.sw{margin-left:auto;display:flex;align-items:flex-end;gap:8px}
#search{background:var(--bg);border:1px solid var(--bd);color:var(--tx);padding:5px 11px;border-radius:8px;font-family:'Syne',sans-serif;font-size:.78rem;width:170px;outline:none}
#search:focus{border-color:var(--gold)}#cb{font-size:.68rem;color:var(--mu);font-family:'DM Mono',monospace;padding-bottom:7px}
.tw{overflow-x:auto;padding-bottom:40px}.view{display:none}.view.active{display:block}
table{width:100%;border-collapse:collapse;font-size:.76rem}
thead th{position:sticky;top:0;z-index:10;background:#0b1223;border-bottom:2px solid var(--gold);padding:9px 13px;text-align:left;font-size:.58rem;text-transform:uppercase;letter-spacing:1.2px;color:var(--gold);white-space:nowrap;cursor:pointer}
thead th:hover{color:var(--g2)}.si{opacity:.35;margin-left:3px}thead th.sorted .si{opacity:1}
tbody tr{border-bottom:1px solid var(--bd);transition:background .1s}tbody tr:hover{background:#0f1e38}
td{padding:7px 13px;white-space:nowrap}td.nm{white-space:normal;max-width:220px;font-weight:500}
td.bi{color:var(--g2);font-weight:700}td.bc{color:var(--bl);font-weight:600}
.pt{font-size:.6rem;font-weight:700;padding:2px 7px;border-radius:4px;text-transform:uppercase}
.pb{background:#1a2e0a;color:#86efac}.pz{background:#2a1040;color:#c4b5fd}.ps{background:#2a1010;color:#fca5a5}
.pr{font-family:'DM Mono',monospace;font-weight:700;color:var(--gn)}
.mr{font-family:'DM Mono',monospace;font-size:.68rem;color:#4b5e7a;text-decoration:line-through}
.dh{color:var(--gn);font-weight:700}.dm{color:var(--gold);font-weight:600}.dl{color:var(--mu)}.dn{color:#374151}
.bi2{background:#1a2e0a;color:#86efac;font-size:.58rem;padding:1px 7px;border-radius:10px;font-weight:700}
.bc2{background:#12213a;color:var(--bl);font-size:.58rem;padding:1px 7px;border-radius:10px}
.na{color:#2d3f5a;font-family:'DM Mono',monospace;font-size:.68rem}
.win{background:#0d2010;color:var(--gn);font-weight:700}.los{color:#4b5e7a}
#empty{text-align:center;padding:50px;color:var(--mu);display:none}
</style></head><body>
<header>
  <div class="logo"><div class="lm">₹</div>
  <div><h1>ITC Q-Commerce Price Tracker</h1>
  <div class="sub">Atta · Nimyle · Yippee · Shower Gel · vs Competitors</div></div></div>
  <div class="rt">Updated<br><span id="rdt"></span></div>
</header>
<div class="stats">
  <div class="stat"><div class="sv" id="ss">—</div><div class="sl">SKUs</div></div>
  <div class="stat"><div class="sv" id="sf">—</div><div class="sl">Found</div></div>
  <div class="stat"><div class="sv" id="sd">—</div><div class="sl">Avg ITC Disc%</div></div>
  <div class="stat"><div class="sv" id="sc">—</div><div class="sl">Cheapest Platform</div></div>
  <div class="stat"><div class="sv" id="sv2">—</div><div class="sl">ITC vs Comp Δ%</div></div>
</div>
<div class="tabs">
  <div class="tab active" data-view="v1">💰 Price Tracker</div>
  <div class="tab" data-view="v2">📊 Discount Analysis</div>
  <div class="tab" data-view="v3">⚔️ ITC vs Competitor</div>
</div>
<div class="filters">
  <div class="fg"><div class="fl">Platform</div><div class="pills" id="fp"></div></div>
  <div class="fg"><div class="fl">Category</div><div class="pills" id="fc"></div></div>
  <div class="fg"><div class="fl">Sub-category</div><div class="pills" id="fs"></div></div>
  <div class="fg"><div class="fl">Brand Type</div><div class="pills" id="ft"></div></div>
  <div class="fg"><div class="fl">Brand</div><div class="pills" id="fb"></div></div>
  <div class="sw"><div><div class="fl">Search</div><input id="search" placeholder="product…"></div><div id="cb">—</div></div>
</div>
<div class="tw">
  <div class="view active" id="v1">
    <table><thead><tr>
      <th data-col="brand">Brand<span class="si">↕</span></th>
      <th data-col="sku_name">Product<span class="si">↕</span></th>
      <th data-col="subcategory">Category<span class="si">↕</span></th>
      <th data-col="platform">Platform<span class="si">↕</span></th>
      <th data-col="sell_price">Best Price↓<span class="si">↕</span></th>
      <th data-col="mrp">MRP<span class="si">↕</span></th>
      <th data-col="discount_pct">Disc%<span class="si">↕</span></th>
      <th data-col="is_itc">Type<span class="si">↕</span></th>
    </tr></thead><tbody id="tb1"></tbody></table>
  </div>
  <div class="view" id="v2">
    <table><thead><tr>
      <th data-col="brand">Brand<span class="si">↕</span></th>
      <th data-col="sku_name">Product<span class="si">↕</span></th>
      <th data-col="mrp">MRP<span class="si">↕</span></th>
      <th data-col="blinkit_price">Blinkit<span class="si">↕</span></th>
      <th data-col="zepto_price">Zepto<span class="si">↕</span></th>
      <th data-col="swiggy_price">Swiggy<span class="si">↕</span></th>
      <th data-col="min_price">Lowest<span class="si">↕</span></th>
      <th data-col="max_disc">Max Disc%<span class="si">↕</span></th>
    </tr></thead><tbody id="tb2"></tbody></table>
  </div>
  <div class="view" id="v3">
    <table><thead><tr>
      <th>Category</th><th>ITC Brand</th><th>ITC Product</th>
      <th>ITC Price</th><th>Competitor</th><th>Comp Product</th>
      <th>Comp Price</th><th>Verdict</th><th>Platform</th>
    </tr></thead><tbody id="tb3"></tbody></table>
  </div>
  <div id="empty">No results match your filters</div>
</div>
<script>
const R=""" + data_str + """;
const S={platform:new Set(['ALL']),category:new Set(['ALL']),sub:new Set(['ALL']),type:new Set(['ALL']),brand:new Set(['ALL']),search:''};
let sc=null,sd=1;
document.getElementById('rdt').textContent=R[0]?.checked_at||'';
const uniq=k=>[...new Set(R.map(r=>r[k]).filter(Boolean))].sort();
function bp(id,key,vals){
  const w=document.getElementById(id);
  ['ALL',...vals].forEach(v=>{
    const p=document.createElement('span');p.className='pill'+(v==='ALL'?' active':'');
    p.textContent=v==='ALL'?'All':v;p.dataset.val=v;
    p.addEventListener('click',()=>tg(key,v,w));w.appendChild(p);
  });
}
function tg(key,val,wrap){
  const s=S[key];
  if(val==='ALL'){s.clear();s.add('ALL');}else{s.delete('ALL');s.has(val)?s.delete(val):s.add(val);if(!s.size)s.add('ALL');}
  wrap.querySelectorAll('.pill').forEach(p=>p.classList.toggle('active',s.has(p.dataset.val)));render();
}
function fr(){
  return R.filter(r=>{
    if(!S.platform.has('ALL')&&!S.platform.has(r.platform))return false;
    if(!S.category.has('ALL')&&!S.category.has(r.category))return false;
    if(!S.sub.has('ALL')&&!S.sub.has(r.subcategory))return false;
    if(!S.type.has('ALL')){if(S.type.has('ITC')&&!r.is_itc)return false;if(S.type.has('Competitor')&&r.is_itc)return false;}
    if(!S.brand.has('ALL')&&!S.brand.has(r.brand))return false;
    if(S.search){const q=S.search.toLowerCase();if(!(r.sku_name||'').toLowerCase().includes(q)&&!(r.brand||'').toLowerCase().includes(q))return false;}
    return true;
  });
}
function pivot(rows){
  const m={};
  rows.forEach(r=>{if(!r.sell_price)return;const k=r.sku_id;
    if(!m[k])m[k]={...r,blinkit_price:null,zepto_price:null,swiggy_price:null};
    if(r.platform==='Blinkit')m[k].blinkit_price=r.sell_price;
    if(r.platform==='Zepto')m[k].zepto_price=r.sell_price;
    if(r.platform==='Swiggy Instamart')m[k].swiggy_price=r.sell_price;
  });
  return Object.values(m).map(r=>{
    const ps=[r.blinkit_price,r.zepto_price,r.swiggy_price].filter(Boolean);
    r.min_price=ps.length?Math.min(...ps):null;
    r.max_disc=r.min_price?Math.round((1-r.min_price/r.mrp)*100):null;
    return r;
  });
}
const PAIRS=[
  ['Atta','Aashirvaad','Patanjali'],['Atta','Aashirvaad','Aashirvad'],
  ['Floor Cleaner','Nimyle','Lizol'],['Floor Cleaner','Nimyle','Harpic'],
  ['Noodles','Yippee','Maggi'],
  ['Shower Gel','Fiama','Dove'],
];
function comps(rows){
  return PAIRS.map(([sub,ib,cb])=>{
    const ir=rows.filter(r=>r.is_itc&&r.brand===ib&&r.subcategory===sub&&r.sell_price);
    const cr=rows.filter(r=>!r.is_itc&&r.brand===cb&&r.subcategory===sub&&r.sell_price);
    if(!ir.length||!cr.length)return null;
    const i=ir.reduce((a,b)=>a.sell_price<=b.sell_price?a:b);
    const c=cr.reduce((a,b)=>a.sell_price<=b.sell_price?a:b);
    const d=c.sell_price?Math.round((i.sell_price-c.sell_price)/c.sell_price*100):null;
    return{sub,ib,is:i.sku_name,ip:i.sell_price,ipl:i.platform,cb,cs:c.sku_name,cp:c.sell_price,cpl:c.platform,d};
  }).filter(Boolean);
}
function dc(d){return d===null?'dn':d>=15?'dh':d>=5?'dm':'dl';}
function pc(p){return p==='Blinkit'?'pb':p==='Zepto'?'pz':'ps';}
function prc(p){return p?`<span class="pr">₹${p}</span>`:'<span class="na">—</span>';}
function stats(rows){
  const skus=new Set(rows.map(r=>r.sku_id)).size;
  const found=rows.filter(r=>r.sell_price).length;
  const ir=rows.filter(r=>r.is_itc&&r.sell_price&&r.discount_pct!==null);
  const avg=ir.length?Math.round(ir.reduce((a,b)=>a+b.discount_pct,0)/ir.length):0;
  const ps={};rows.filter(r=>r.sell_price).forEach(r=>{ps[r.platform]=(ps[r.platform]||0)+1;});
  const cp=Object.entries(ps).sort((a,b)=>b[1]-a[1])[0];
  const ia=rows.filter(r=>r.is_itc&&r.sell_price);
  const ca=rows.filter(r=>!r.is_itc&&r.sell_price);
  const iav=ia.length?ia.reduce((s,r)=>s+r.sell_price,0)/ia.length:0;
  const cav=ca.length?ca.reduce((s,r)=>s+r.sell_price,0)/ca.length:0;
  const dv=cav?Math.round((iav-cav)/cav*100):0;
  document.getElementById('ss').textContent=skus;
  document.getElementById('sf').textContent=found;
  document.getElementById('sd').textContent=avg+'%';
  document.getElementById('sc').textContent=cp?cp[0].split(' ')[0]:'—';
  document.getElementById('sv2').textContent=(dv>=0?'+':'')+dv+'%';
  document.getElementById('cb').textContent=rows.length+' rows';
}
function render(){
  const rows=fr().sort((a,b)=>{if(!sc)return 0;const va=a[sc]??'',vb=b[sc]??'';return va<vb?-sd:va>vb?sd:0;});
  stats(rows);
  document.getElementById('empty').style.display='none';
  document.getElementById('tb1').innerHTML=rows.map(r=>`<tr>
    <td class="${r.is_itc?'bi':'bc'}">${r.brand}</td><td class="nm">${r.sku_name}</td>
    <td style="color:var(--mu);font-size:.7rem">${r.subcategory}</td>
    <td><span class="pt ${pc(r.platform)}">${r.platform}</span></td>
    <td>${r.sell_price?`<span class="pr">₹${r.sell_price}</span>`:'<span class="na">—</span>'}</td>
    <td><span class="mr">₹${r.mrp}</span></td>
    <td class="${dc(r.discount_pct)}">${r.discount_pct!==null?r.discount_pct+'%':'—'}</td>
    <td>${r.is_itc?'<span class="bi2">ITC</span>':'<span class="bc2">Comp</span>'}</td>
  </tr>`).join('');
  document.getElementById('tb2').innerHTML=pivot(rows).map(r=>`<tr>
    <td class="${r.is_itc?'bi':'bc'}">${r.brand}</td><td class="nm">${r.sku_name}</td>
    <td style="color:#6b82a8;font-family:'DM Mono',monospace">₹${r.mrp}</td>
    <td>${prc(r.blinkit_price)}</td><td>${prc(r.zepto_price)}</td><td>${prc(r.swiggy_price)}</td>
    <td>${r.min_price?`<span class="pr">₹${r.min_price}</span>`:'<span class="na">—</span>'}</td>
    <td class="${dc(r.max_disc)}">${r.max_disc!==null?r.max_disc+'%':'—'}</td>
  </tr>`).join('');
  document.getElementById('tb3').innerHTML=comps(rows).map(r=>{
    const w=r.d!==null&&r.ip<=r.cp;
    return`<tr>
      <td style="color:var(--mu);font-size:.7rem">${r.sub}</td>
      <td class="bi">${r.ib}</td><td class="nm">${r.is}</td>
      <td class="${w?'win':'los'}">${r.ip?'₹'+r.ip:'—'}</td>
      <td class="bc">${r.cb}</td><td class="nm">${r.cs}</td>
      <td class="${!w?'win':'los'}">${r.cp?'₹'+r.cp:'—'}</td>
      <td class="${r.d!==null?(r.d<=0?'dh':'dn'):''}">${r.d!==null?(r.d<=0?'✅ ITC cheaper by '+Math.abs(r.d)+'%':'⚠️ ITC costlier by '+r.d+'%'):'—'}</td>
      <td><span class="pt ${pc(r.ipl)}">${r.ipl}</span></td>
    </tr>`;
  }).join('');
  if(!rows.length)document.getElementById('empty').style.display='block';
}
document.querySelectorAll('.tab').forEach(t=>{
  t.addEventListener('click',()=>{
    document.querySelectorAll('.tab,.view').forEach(x=>x.classList.remove('active'));
    t.classList.add('active');document.getElementById(t.dataset.view).classList.add('active');
  });
});
document.querySelectorAll('thead th[data-col]').forEach(th=>{
  th.addEventListener('click',()=>{
    const col=th.dataset.col;sc===col?sd*=-1:(sc=col,sd=1);
    document.querySelectorAll('thead th').forEach(t=>t.classList.remove('sorted'));
    th.classList.add('sorted');th.querySelector('.si').textContent=sd===1?'↓':'↑';render();
  });
});
document.getElementById('search').addEventListener('input',e=>{S.search=e.target.value.trim();render();});
bp('fp','platform',uniq('platform'));bp('fc','category',uniq('category'));
bp('fs','subcategory',uniq('subcategory'));bp('fb','brand',uniq('brand'));
const tw=document.getElementById('ft');
['ALL','ITC','Competitor'].forEach(v=>{
  const p=document.createElement('span');p.className='pill'+(v==='ALL'?' active':'');
  p.textContent=v==='ALL'?'All':v;p.dataset.val=v;
  p.addEventListener('click',()=>tg('type',v,tw));tw.appendChild(p);
});
render();
</script></body></html>"""


# ── MAIN ──────────────────────────────────────────────────────
async def run():
    run_dt = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=5,minutes=30))
    ).strftime("%d %b %Y, %I:%M %p IST")

    best = {}  # (sku_id, platform) → lowest price seen

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"]
        )

        total = len(PINCODES) * len(PLATFORMS)
        done = 0

        for (pincode, area, tier) in PINCODES:
            print(f"\n📍 {pincode} {area}")
            for platform in PLATFORMS:
                done += 1
                print(f"  🏪 {platform} ({done}/{total})")

                ctx = await browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width":random.randint(390,430),"height":random.randint(844,926)},
                    locale="en-IN", timezone_id="Asia/Kolkata",
                    extra_http_headers={"Accept-Language":"en-IN,en;q=0.9"},
                )
                page = await ctx.new_page()
                await page.add_init_script("""
                    Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
                    window.chrome={runtime:{}};
                    Object.defineProperty(navigator,'languages',{get:()=>['en-IN','en']});
                """)

                loc_ok = await set_location(page, pincode, platform)
                if not loc_ok:
                    print(f"    ⚠️  Location failed")
                    await ctx.close()
                    continue

                for sku in SKUS:
                    sp, mr = await scrape_sku(page, sku, platform)
                    key = (sku[0], platform)
                    if sp:
                        ex = best.get(key)
                        if not ex or sp < ex["sell_price"]:
                            best[key] = {"sell_price":sp,"mrp_scraped":mr,"pincode_min":pincode}
                        print(f"    ✅ ₹{sp:<5} {sku[2][:45]}")
                    else:
                        print(f"    ❌       {sku[2][:45]}")
                    await asyncio.sleep(0.4)

                await ctx.close()

        await browser.close()

    results = []
    for sku in SKUS:
        sid,brand,name,cat,sub,mrp,is_itc,_ = sku
        for platform in PLATFORMS:
            b = best.get((sid,platform),{})
            sp = b.get("sell_price")
            disc = round((1-sp/mrp)*100) if sp else None
            results.append({
                "sku_id":sid,"brand":brand,"sku_name":name,
                "category":cat,"subcategory":sub,"mrp":mrp,
                "is_itc":is_itc,"platform":platform,
                "sell_price":sp,"mrp_scraped":b.get("mrp_scraped",mrp),
                "discount_pct":disc,"pincode_min":b.get("pincode_min",""),
                "checked_at":run_dt,
            })

    with open("index.html","w",encoding="utf-8") as f:
        f.write(build_html(results,run_dt))
    with open("last_run.txt","w") as f:
        f.write(run_dt)

    found = sum(1 for r in results if r["sell_price"])
    print(f"\n✅ Done — {found}/{len(results)} prices found.")

if __name__ == "__main__":
    asyncio.run(run())
