# AI Shopping Research Agent (v0.1)

Local-first US shopping research agent. **Python owns ranking.** Local Ollama (default `qwen3:4b-instruct`)  explains the ranked report for the UI.
Category profiles (plug-in): **laptop**, **headphones**.

Proving queries:
- `best laptop under $1000`
- `best wireless earbuds under $100`

Pipeline:

`parse → discover → identify → research → validate → rank` → optional `explain` (Ollama)

### Future (not built yet)

- LLM-assisted discovery (v1-style search leads + Ollama model-name extraction). Keep discovery/ranking evidence-first; do not let the LLM invent leads or scores.
- **Ongoing (partially done):** deeper multi-product page binding. First slice shipped: extract from model-local windows, require manufacturer-page STRONG snippets to name the model, and keep USB-C-cable≠port weak in the auditor. Still open: interleaved multi-SKU pages where another product’s claim sits inside the model window, and richer semantic claim↔model proof beyond proximity/alias checks.
- Optional later: priority-aware scoring weights (today scores stay a fixed evidence heuristic; see **How scoring works**).

## Run (CLI)

```powershell
cd D:\ai-shopping-agent-v2
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = "src"
# PowerShell strips $1000 from double quotes. Prefer --budget:
python -m shopping_agent "best laptop under 1000" --budget 1000
python -m pytest -q
```

Default `pytest` stays mocked/fast. Before a live recording, optionally smoke-check allow-listed manufacturer page hints (reachable + page mentions the model):

```powershell
python -m pytest -m live -q
# or:
$env:SHOPBUDDY_LIVE = "1"
python -m pytest -m live -q
```

Blocked / timed-out / unreachable hosts are skipped (geo-block, 403, rate-limits). Dead slugs (404) or pages that omit the model fail. Not a hard CI gate.

Default run uses **local fixtures** so it works without API keys. Report: `output/latest_report.json`.

## Run (ShopBuddy UI)

**ShopBuddy** is a 2-page Streamlit app: Search → Picks (grid).

```powershell
cd D:\ai-shopping-agent-v2
$env:PYTHONPATH = "src"
.\.venv\Scripts\streamlit.exe run app.py
```

UI controls:
- **Local model** dropdown (from `ollama list`)
- **Live** vs **Fixtures** discovery
- **Include SerpApi** (off by default; turn on for a fuller live recording)

You do **not** need to brand eBay/SerpApi on camera — they are just listing sources.

### Ollama on GPU (recommended)

If Ollama pegs CPU at 100%, restart it with Vulkan/iGPU flags **before** running ShopBuddy:

If `.ps1` is blocked by execution policy, use the `.cmd` helper or paste the commands:

```powershell
# Stop any existing Ollama process first (optional):
# Get-Process ollama* -ErrorAction SilentlyContinue | Stop-Process -Force

cd D:\ai-shopping-agent-v2
.\scripts\start_ollama_gpu.cmd
```

Or manually:

```powershell
$env:OLLAMA_VULKAN = "1"
$env:OLLAMA_IGPU_ENABLE = "1"
ollama serve
```

Keep that terminal open. Explanations soft-skip if Ollama is offline.

## Live discovery and page checks

Copy `.env.example` values into your environment, then:

```powershell
$env:PYTHONPATH = "src"
# Prefer eBay-only while SerpApi credits are limited:
python -m shopping_agent "best laptop under 1000" --budget 1000 --live --no-fixtures --skip-serpapi
```

- `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` — eBay Browse API
- `SERPAPI_API_KEY` — Google Shopping via SerpApi

### SerpApi quota (important)

eBay is the primary live source. SerpApi is a small supplement with a hard per-run cap:

- `SERPAPI_MAX_CALLS=5` total HTTP requests per run (laptop **or** headphones)
- Default split: **1** shopping search + up to **4** detail lookups
- Override for one run: `--serpapi-max-calls 5`

So two live demos (laptop + headphones) use about **10** SerpApi credits max.  
Use `--skip-serpapi` to spend **0** SerpApi credits (eBay + manufacturer pages only).

`--live` also fetches allow-listed manufacturer pages for specs and retailer pages for unverified prices. Missing keys are recorded as source errors. A blocked page is recorded as inaccessible and is not retried.

## What this version does

- Parse a request into a registered category profile (`laptop` or `headphones`), US market, and budget.
- Discover from that profile's fixtures, and from eBay plus SerpApi when `--live` and keys are set.
- eBay runs profile-targeted brand/model queries and prefers recognizable titles.
- SerpApi resolves Google Shopping shells to real retailer offer URLs via Immersive/Product APIs.
- Identify an allow-listed model and configuration for the active profile.
- Research profile-specific specs from fixtures or manufacturer pages.
- Validate evidence strength, apply listing↔manufacturer consistency, and corroborate prices when needed.
- Rank eligible offers with that profile’s **fixed evidence heuristic** (not personalized preference weights).
- Return up to five recommendations and say when the shortlist is provisional.

### How scoring works

Scores are **fixed evidence points**, not a personalized “best battery / best sound / best value” ranking.

| Category | What earns points | Not scored (recorded only) |
|---|---|---|
| **Headphones** | Strong manufacturer ANC (+20), type (+10), charging port (+5); verified new (+3) / used-refurb (−5) | Battery life; comfort; sound quality; “value” |
| **Laptops** | Strong manufacturer RAM/storage/CPU/display/GPU (plus reduced listing-title fallbacks for some fields); condition ± | Battery life |

- Report `request.priorities` are **descriptive category focus areas** (`priorities_role: descriptive_category_focus_only`). They do **not** reweight scores.
- The only earbuds personalization today is a hard form-factor filter: `prefer_true_wireless` when the query asks for earbuds (excludes over/on-ear).
- ShopBuddy labels scores as **evidence points** and surfaces the scoring limitations on the Picks page.

### Adding a 3rd category later

1. Copy `profiles/headphones.py` as a template → `profiles/<name>.py`
2. Register it in `profiles/registry.py`
3. Add `data/fixtures/<name>_listings.json` and `<name>_specs.json`
4. Shared pipeline stages stay untouched

## Honest limits

- A listed item price is not a delivered total unless the page states an order total.
- Scores are fixed evidence-backed spec points for the category, not overall product quality and not personalized to profile priorities.
- The shortlist is the best eligible set from the candidate pool by that heuristic, not the whole US market.
- Ollama narrates the report only; it does not change scores or invent specs.
- Add another category by creating `profiles/<name>.py` and registering it in `profiles/registry.py`.
