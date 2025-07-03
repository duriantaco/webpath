# Webpath

![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)
![100% Local](https://img.shields.io/badge/privacy-100%25%20local-brightgreen)
![Security Policy](https://img.shields.io/badge/security-policy-brightgreen)
![Skylos Check](https://img.shields.io/badge/Dead_Code-Free-brightgreen?logo=moleculer&logoColor=white)

HTTP library that makes APIs actually enjoyable to work with

* **JSON shortcuts** - `find()`, `find_all()`, `extract()` with dot notation
* **Request logging** - Auto request/response logging
* **Smart caching** - Filters some sensitive headers automatically
* **Advanced pagination** - Cycle detection and next-page finding

## Why webpath?

**vs requests/httpx:**
- Manual JSON navigation: `resp.json()["data"]["users"][0]["name"]`
- Intuitive shortcuts: `resp.find("data.users.0.name")`

**vs other URL builders:**
- No HTTP client integration
- Easier URL building + requests + JSON processing

**vs debugging tools:**
- Separate tools for logging/inspection
- Built-in logging, response inspection, cURL generation

## Installation

```bash
# core features
pip install webpath

# async helpers (adds httpx)
pip install "webpath[async]"

# progress bar downloads (adds tqdm)
pip install "webpath[progress]"

```

## Quick Start

### Python API

#### Build URLs like pathlib.Path

```python
base  = WebPath("https://api.example.com/v1")
user  = base / "users" / 42
print(user) # https://api.example.com/v1/users/42
```

#### Add query params
```python
detail = user.with_query(fields=["name", "email"])
print(detail) 
# …/42?fields=name&fields=email
```

#### One liner GET
```python
resp = detail.get(timeout=5).json()
print(resp["name"])
```

#### auto retries + back off
```python
html = WebPath("https://httpbin.org/status/503").get(retries=3, backoff=0.5).text
```

#### reuse a single session
```python
with detail.session() as call:
    a = call("get").json()
    b = call("post", json={"hello": "world"}).json()
```

#### async request (requires webpath[async])
```python
import asyncio

async def main():
    data = await detail.aget(timeout=5)
    print(data.json())

asyncio.run(main())
```

#### download with progress + checksum
```python
url  = WebPath("https://speed.hetzner.de/100MB.bin")
path = url.download("100MB.bin", progress=True,
                    checksum="5be551ef1ce3…")
print("saved to", path)

```

### CLI Usage

#### Join path segments
```bash
webpath join https://api.example.com/v1 users 42
#### https://api.example.com/v1/users/42
```

#### simple GET (stdout)
```bash
webpath get https://api.github.com/repos/python/cpython -p | jq '.stargazers_count'
```

#### GET with retry/back off
```bash
webpath get https://httpbin.org/status/503 --retries 3 --backoff 0.5
```

#### download with retries, back off and checksum
```bash
webpath download https://speed.hetzner.de/100MB.bin 100MB.bin \
                 --retries 4 --backoff 0.5 \
                 --checksum blahblahblah…
```

### Flags for cli
```
Options:

Flag	Description	Default
-p, --pretty	Pretty-print JSON responses	off
-r, --retries	Number of retry attempts	0
-b, --backoff	Back off factor in seconds	0.3
```

# WebPath Tutorial — *Building a Tiny Crypto Dashboard with the CoinGecko API*

## 1  |  CoinGecko’s API

CoinGecko exposes an **unauthenticated** REST API at  
`https://api.coingecko.com/api/v3/`.

Most market endpoints live under `/coins/markets`.  
Example (unfriendly style):

```
GET https://api.coingecko.com/api/v3/coins/markets
     ?vs_currency=usd
     &ids=bitcoin,ethereum,dogecoin
     &order=market_cap_desc
     &per_page=3
     &page=1
     &sparkline=false
```

---

## 2  |  Step by step with WebPath

```python
from webpath import WebPath

# create a base path (it behaves like pathlib.Path)
api = WebPath("https://api.coingecko.com/api/v3")

markets = api / "coins" / "markets"

# attach query parameters in plain Python
coins   = ["bitcoin", "ethereum", "dogecoin", "matic-network"]
params  = dict(
    vs_currency = "usd",
    ids         = ",".join(coins),
    order       = "market_cap_desc",
    per_page    = len(coins),
    sparkline   = "false"
)
url = markets.with_query(**params)

print(url)
# -> https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=bitcoin,...
```

### Quick sanity check

```python
print(url.curl())
url.inspect()

### What it looks like

┌──────── Response ────────┐
│ 200 OK * 147 ms * 3 KB   │
└──────────────────────────┘
┌──────── Response Body ───┐
{                          |
  "id": "bitcoin",         |
  "name": "Bitcoin",       |
  …                        |
└──────────────────────────┘
┌──────── Headers ─────────┐
content-type  application/json
…
└──────────────────────────┘
</details>

```

---

## 3  |  Fetching & Caching

```python
data = url.with_cache(ttl=120).get().json()

# .. second call < 2 min later is served instantly from disk
```

*The cache is stored in `~/.webpath/cache` by default and strips auth headers automatically.*

---

## 4  |  Extraction

Each coin object looks like (truncated):

```json
{
  "id": "bitcoin",
  "symbol": "btc",
  "name": "Bitcoin",
  "current_price": 68123,
  "price_change_percentage_24h": -2.17,
  ...
}
```

You can use normal indexing *or* WebPath’s helpers:

```python
rows = []
for coin in data:
    r = WebPath.from_json(coin)
    rows.append((
        r["name"],
        f"${r['current_price']:,}",
        f"{r.find('price_change_percentage_24h'):+.2f} %"
    ))
```

---

## 5  |  Print a Table (optional)

```python
from tabulate import tabulate
from rich.console import Console

console = Console()

rows.sort(key=lambda x: float(x[2].replace('%', '')), reverse=True)

console.print(
    tabulate(rows, headers=["Coin", "Price (USD)", "24 h %"], tablefmt="rounded_outline")
)

## Sample output**

╭────────┬──────────────┬─────────╮
│ Coin   │ Price (USD)  │ 24 h %  │
├────────┼──────────────┼─────────┤
│ Dogecoin │ $0.245     │ +3.18 % │
│ Bitcoin  │ $68,123    │ -2.17 % │
│ …        │ …          │ …       │
╰────────┴──────────────┴─────────╯
```

---

## 6  |  Making It Reusable

Create a tiny helper module `crypto.py`:

```python
from webpath import WebPath

API = WebPath("https://api.coingecko.com/api/v3") / "coins" / "markets"

def get_market(coins, currency="usd", ttl=120):
    url = API.with_query(
        vs_currency=currency,
        ids=",".join(coins),
        order="market_cap_desc",
        per_page=len(coins),
        sparkline="false"
    ).with_cache(ttl=ttl)
    return url.get().json()
```

Now in any script / notebook:

```python
from crypto import get_market
print(get_market(["solana", "toncoin"], "eur")[0]["current_price"])
```

---

## 7  |  Going Further

1. **Pagination** – CoinGecko allows `page=`; chain `.paginate()` to stream *everything*
2. **Async** – replace `.get()` with `.aget()` inside `get_market` after  
   `pip install "webpath[async]"`
3. **Retries/Back off** – `url.get(retries=3, backoff=0.5)` for flaky networks
4. **Downloads** – Need historical CSV dumps? Use `.download()` with checksums
5. **CLI** – `webpath get "$(crypto_url)" -p` to poke around quickly

---

## Finished!

*Questions? Bugs?* -> [GitHub Issues](https://github.com/duriantaco/webpath/issues)