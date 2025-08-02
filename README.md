# WebPath

![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)
![100% Local](https://img.shields.io/badge/privacy-100%25%20local-brightgreen)
![Security Policy](https://img.shields.io/badge/security-policy-brightgreen)

A Python HTTP client library that makes interacting with APIs with lesser boilerplate. Built on `httpx` and `jmespath`.

* **`Client` Interface**: Manage sessions, headers, and retries centrally
* **JSON Traversal**: Use `jmespath` expressions to find whatever you need
* **Async**: `async` and `await` support
* **Caching & Retries**: Features with simple controls
* **Path-like URL Building**: Construct URLs with a clean, intuitive `/` operator.

---

## The `webpath` Workflow

`webpath` tries to integrate the lifecycle of an API request. Eg, from building the URL to processing the response.

### **Without `webpath`** 

You manually wire together multiple libraries and steps as shown in the example below:

```python
import httpx
import jmespath

# step 1 manual configuration
transport = httpx.HTTPTransport(retries=3)
client = httpx.Client(
    base_url="[https://api.github.com](https://api.github.com)",
    headers={"Accept": "application/vnd.github.v3+json"},
    transport=transport
)

# step 2 build the url
url = "/repos/python/cpython"

# step 3 make the request
response = client.get(url)
response.raise_for_status()
data = response.json()

description = jmespath.search("description", data)
print(description)
```

### **With** webpath

The entire process is a single chain managed by `Client`:

```Python

from webpath.core import Client

# step 1.. create a reusable client for the API
with Client(
    "[https://api.github.com](https://api.github.com)",
    headers={"Accept": "application/vnd.github.v3+json"},
    retries=3
) as api:
    # step 2.. find the data in one line
    description = api.get("repos", "python", "cpython").find("description")
    print(description)
```

# Installation

# Core features (includes httpx and jmespath)
pip install webpath

# For progress bar on downloads
pip install "webpath[progress]"

# Quick Start

## Client Usage 

```python
from webpath.core import Client
import asyncio

# step 1. Create the client with a base URL, shared headers, and retries
#    The client can be used for the lifetime of your application.
api = Client(
    "[https://api.github.com](https://api.github.com)",
    headers={"Accept": "application/vnd.github.v3+json"},
    retries=3,
    timeout=10.0
)

# step 2. make sync requests
repo_info = api.get("repos", "python", "cpython")
print(f"Repo Description: {repo_info.find('description')}")

# step 3. make async requests
async def get_user_name():
    user_info = await api.aget("users", "torvalds")
    print(f"User's Name: {user_info.find('name')}")

asyncio.run(get_user_name())


# step 4. use the context manager to ensure connections are closed
try:
    with Client("[https://httpbin.org](https://httpbin.org)", retries=2) as http:
        http.get("status/503")
except Exception as e:
    print(f"\nRequest failed as expected: {e}")
finally:
    ## **Always close the client when you're done**
    api.close()
```

## Retries with a Pluggable Policy

```python
import httpx

## create your custom backoff logic
def retry_backoff(response):
    if "Retry-After" in response.headers:
        wait_time = float(response.headers["Retry-After"])
        print(f"rate limited, sleeping {wait_time}s")
        return wait_time

## pass your custom logic into client
with Client("https://httpbin.org", retries=retry_backoff) as client:
    try:
        client.get("status/429")
    except httpx.HTTPStatusError as e:
        print(f"still failed: {e}")
```

# Core Features

* Client-based Sessions: Manages connection pooling, default headers, retries, caching, and rate limiting for the API
* URL Building: Chain path segments with the `/` operator (e.g. `api/"users"/123`).
* JSON Traversal: A jmespath-powered find() method lets you query complex JSON (e.g., resp.find("users[?age > 18].name")) . -- In future may change to `jonq` when the library is more stable
* Async: Full async/await support for all HTTP verbs (aget, apost, etc.)
* Retries: `Client` will auto handle transient network or server errors 
* Response Caching: Add `.with_cache(ttl=120)` to any request to cache the response
* File Downloads: `.download()` method with progress bars and checksum validation
* Rate Limiting: Automatically throttle requests with `.with_rate_limit(requests_per_second=1)`.


# Full Tutorial: Using the CoinGecko API

## This tutorial will show you how to fetch cryptocurrency data using `webpath`

1. Set Up the API Client

First, create a Client (this is reusable) for the CoinGecko API. We'll set a 60-second TTL for caching

```python

from webpath.core import Client

api = Client("[https://api.coingecko.com/api/v3](https://api.coingecko.com/api/v3)", cache_ttl=60)
```

2. Fetch Market Data

Now use the client to hit the endpoint. We can build the path and add query parameters in one call

```python
coins = ["bitcoin", "ethereum", "dogecoin"]

# build your path + query params
market_data = api.get(
    "coins", "markets",
    params={
        "vs_currency": "usd",
        "ids": ",".join(coins),
        "order": "market_cap_desc"
    }
)
```

3. Extract Data with `find()`
The response is a JSON array of objects. We can use `find()` with a `jmespath` expression to extract the names and prices from all coins

```python

# jmes expression to get name and price
expression = "[*].{name: name, price: current_price}"

extracted_data = market_data.find(expression)

for coin in extracted_data:
    print(f"{coin['name']}: ${coin['price']:,}")

## output example:
## bitcoin: $120,000.00
## ethereum: $5,432.00
## dogecoin: $0.123
```

# CLI Usage

* Join path segments

```bash
webpath join [https://api.example.com/v1](https://api.example.com/v1) users 42
# [https://api.example.com/v1/users/42](https://api.example.com/v1/users/42)
```

* Simple-Get

```bash
webpath get [https://api.github.com/repos/python/cpython](https://api.github.com/repos/python/cpython) -p | jq '.stargazers_count'
```

* Get with retries

```bash
webpath get [https://httpbin.org/status/503](https://httpbin.org/status/503) --retries 3
```

* Download 

```bash
webpath download [https://speed.hetzner.de/100MB.bin](https://speed.hetzner.de/100MB.bin) 100MB.bin --checksum "5be551ef..."
```