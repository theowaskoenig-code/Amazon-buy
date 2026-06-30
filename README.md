# Amazon Autobuyer — Midea PortaSplit restock bot

Watches a single Amazon product page and **automatically completes checkout** the
instant it becomes buyable — built for grabbing a Midea PortaSplit (ASIN
`B0GX16LKSC`) on amazon.de that sells out within seconds of restocking.

It buys only when **all** of your criteria are met:

- in stock (a Buy-Now / Add-to-Cart button is present),
- **sold by the seller you require** (default: `Midea`),
- **price at or below your cap** (default: `€1199`),
- any colour variant is acceptable (it scans the colour swatches).

---

## ⚠️ Read this first

- **Terms of Service / account risk.** Amazon's Conditions of Use prohibit
  automated ordering. Your account could be flagged, an order reversed, or worse.
  This is a personal-use tool you run **at your own risk**. It polls politely
  (randomised interval) and **pauses** on CAPTCHA/2FA rather than trying to defeat
  it, to keep things low-key — but the risk is real and yours.
- **It runs on YOUR machine**, not in the cloud. It drives a real Chromium browser
  logged into your Amazon account.
- **Safety rails are on by default:** `dry_run: true` (never buys until you flip
  it) and a hard `max_price` guard. Prove it works before trusting it with money.

---

## Setup (macOS / Mac mini)

```bash
# 1. Get the code
git clone <this-repo> && cd Amazon-buy

# 2. Create a virtualenv and install
python3 -m venv .venv && source .venv/bin/activate
pip install -e .            # installs deps + the `autobuyer` command
playwright install chromium # one-time browser download

# 3. Create your config
cp config.example.yaml config.yaml
#   edit config.yaml — the product_url is already set to the Midea ASIN.
#   set required_seller, max_price, etc. to taste.
```

## Usage

```bash
autobuyer login   # opens Amazon — log in + pass 2FA ONCE. Session is saved.
autobuyer check   # one-shot: prints the current price/seller/stock + buy verdict
autobuyer run     # watches the page; checks out when your criteria are met
```

`autobuyer run` honours `dry_run` from the config. To force a real purchase from
the command line regardless of config, use `autobuyer run --live`.

### Recommended path (do this in order)

1. **`autobuyer login`** — log in once; the session persists in `user_data/`.
2. **Dry-run check** — keep `dry_run: true`, run `autobuyer run`. It should report
   the Midea page as out-of-stock right now and keep watching. When something is
   buyable it walks all the way to the order-review screen, logs
   **"WOULD place order"**, screenshots it, and stops — *without buying*.
3. **Cheap-item live POC** — point `product_url` at a random cheap **in-stock**
   item, set `required_seller: ""` (so the seller check is skipped) and `max_price`
   just above its price, set `dry_run: false`, and run. It will **really buy** it
   through the exact same Buy-Now → Place-Order path. **Cancel the order afterward.**
   This proves the live flow end-to-end with a few euros at risk instead of €1199.
4. **Go live for real** — restore the Midea settings in `config.yaml`
   (`product_url` = the Midea ASIN, `required_seller: Midea`, `max_price: 1199`,
   `dry_run: false`) and leave `autobuyer run` going. Keep the laptop awake.

> Tip: on macOS, prevent sleep while it runs with `caffeinate -s autobuyer run`.

## Configuration (`config.yaml`)

| key | meaning |
|---|---|
| `product_url` | the page to watch (Midea ASIN `B0GX16LKSC` by default) |
| `required_seller` | buy only if the buy-box seller contains this (`""` = any) |
| `max_price` | hard cap in EUR; never pays more |
| `any_color` | if `true`, tries other colour swatches when one is sold out |
| `poll_min_seconds`/`poll_max_seconds` | randomised reload interval (politeness) |
| `dry_run` | `true` = stop before the final click; `false` = actually buy |
| `headless` | keep `false` so you can watch and solve CAPTCHAs |

## How it works

```
monitor.run()  ── reload product page every 4–9s (jittered)
   └─ detect.inspect(page)     read title / price / seller / availability
   └─ detect.evaluate(...)     pure pass/fail against your criteria
        └─ if buyable → checkout.buy_now(page)
             click Buy Now → order-review screen → place order
             (dry-run stops here and logs "WOULD place order")
```

Selectors live in `src/autobuyer/selectors.py` — that's the first place to tweak
if Amazon changes its page markup.

## Tests

Pure logic + browser-backed selector/checkout tests (the browser ones drive real
Chromium against local HTML fixtures — no Amazon access needed):

```bash
pip install -e ".[dev]"
pytest            # 25 tests: price parsing, criteria, selectors, dry-run gate
```

## Limitations

- CAPTCHA / OTP will interrupt; the bot pauses and asks you to solve it, then resumes.
- If Amazon redesigns the product or checkout page, update `selectors.py`.
- One purchase, then it stops (buy-once).
