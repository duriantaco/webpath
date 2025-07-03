from __future__ import annotations

import contextlib
from typing import Any
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import contextvars
import atexit
import httpx
from typing import Type, TypeVar, Any
from pydantic import TypeAdapter, ValidationError
import warnings, os
from urllib.parse import urlsplit
import json
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.panel import Panel
from rich import box

T = TypeVar("T")
_client_cv = contextvars.ContextVar("webpath_client", default=None)

_HTTP_VERBS = ("get", "post", "put", "patch", "delete", "head", "options")
_HTTP_SCHEMES = ("http", "https")

class CachedResponse:
    def __init__(self, cached_data: dict):
        self.status_code = cached_data['status_code']
        self.headers = cached_data['headers']
        self.content = cached_data['content'].encode('utf-8')
        self.text = cached_data['content']
        self.url = cached_data['url']
    
    def json(self):
        return json.loads(self.content)
    
    def raise_for_status(self): # pragma: no skylos
        if 400 <= self.status_code < 600:
            raise requests.HTTPError(f"{self.status_code} Client Error")
        
class WebResponse:
    def __init__(self, response, parent_path):
        self._response = response
        self._parent = parent_path
        self._json_data = None
    
    def __getattr__(self, name):
        return getattr(self._response, name)
    
    def find(self, path: str, default=None):
        if not path:
            return default
        
        data = self.json_data
        if not data:
            return default
        
        try:
            parts = self._parse_path(path)
            current = data
            
            for part in parts:
                if isinstance(current, dict):
                    if isinstance(part, int):
                        part = str(part)
                    current = current[part]
                elif isinstance(current, list):
                    if isinstance(part, str):
                        if part.isdigit():
                            part = int(part)
                        else:
                            return default
                    current = current[part]
                else:
                    return default
                    
            return current
            
        except (KeyError, IndexError, TypeError, ValueError):
            return default

    def find_all(self, pattern: str):
        if not pattern:
            return []
        
        data = self.json_data
        if not data:
            return []
        
        parts = self._parse_path(pattern)
        return self._find_recursive([data], parts, 0)

    def search(self, key: str, case_sensitive: bool = False):
        if not key:
            return []
        
        data = self.json_data
        if not data:
            return []
        
        search_key = key if case_sensitive else key.lower()
        return self._search_recursive(data, search_key, case_sensitive)

    def extract(self, *paths, flatten: bool = False): # pragma: no skylos
        results = []
        for path in paths:
            if '*' in path:
                values = self.find_all(path)
                if flatten:
                    results.extend(values)
                else:
                    results.append(values)
            else:
                results.append(self.find(path))
        
        return tuple(results) if len(results) > 1 else results[0] if results else None

    def has_path(self, path: str) -> bool:
        return self.find(path, default=object()) is not object()

    def _parse_path(self, path: str):
        if not path:
            return []
        
        parts = []
        for part in path.split('.'):
            if part.isdigit():
                parts.append(int(part))
            else:
                parts.append(part)
        return parts

    def _find_recursive(self, current_items, parts, part_index):
        if part_index >= len(parts):
            return current_items
        
        current_part = parts[part_index]
        next_items = []
        
        for item in current_items:
            if current_part == '*':
                # wildcard .. collect all items
                if isinstance(item, dict):
                    next_items.extend(item.values())
                elif isinstance(item, list):
                    next_items.extend(item)
            else:
                try:
                    if isinstance(item, dict):
                        if isinstance(current_part, int):
                            current_part = str(current_part)
                        if current_part in item:
                            next_items.append(item[current_part])
                    elif isinstance(item, list):
                        if isinstance(current_part, str) and current_part.isdigit():
                            current_part = int(current_part)
                        if isinstance(current_part, int) and 0 <= current_part < len(item):
                            next_items.append(item[current_part])
                except (KeyError, IndexError, TypeError):
                    continue
        
        if part_index == len(parts) - 1:
            return next_items
        else:
            return self._find_recursive(next_items, parts, part_index + 1)

    def _search_recursive(self, obj, search_key, case_sensitive):
        results = []
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_to_check = key if case_sensitive else key.lower()
                if search_key in key_to_check:
                    results.append(value)
                
                if isinstance(value, (dict, list)):
                    results.extend(self._search_recursive(value, search_key, case_sensitive))
                    
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    results.extend(self._search_recursive(item, search_key, case_sensitive))
        
        return results

    def get_errors(self):
        return self.search("error") + self.search("message") + self.search("detail")

    def get_ids(self):
        return self.search("id")

    def get_pagination_info(self):
        return {
            'next': self.find("next") or self.find("next_url") or self.find("pagination.next"),
            'prev': self.find("prev") or self.find("prev_url") or self.find("pagination.prev"),
            'total': self.find("total") or self.find("count") or self.find("pagination.total"),
            'page': self.find("page") or self.find("pagination.page"),
            'per_page': self.find("per_page") or self.find("limit") or self.find("pagination.per_page")
        }
    
    @property
    def json_data(self):
        if self._json_data is None:
            try:
                self._json_data = self._response.json()
            except:
                self._json_data = {}
        return self._json_data
    
    def json(self):
        return self._response.json()
    
    def parse(self, model: Type[T] | None = None, *, strict: bool | None = None) -> T | Any:
        data = self.json()

        if model is None:
            return data

        strict = strict if strict is not None else os.getenv("WEBPATH_VALIDATION") == "strict"

        try:
            return TypeAdapter(model).validate_python(data)
        except ValidationError as exc:
            if strict:
                raise
            warnings.warn(f"Validation failed – returning raw data: {exc}")
            return data
        
    def __truediv__(self, key):
        from .core import WebPath
        data = self.json_data
        
        if isinstance(data, dict) and key in data:
            value = data[key]
            if isinstance(value, str) and value.startswith(('http://', 'https://')):
                if not getattr(self._parent, '_allow_auto_follow', False):
                    return value
                
                parsed = urlparse(value)
                if parsed.hostname in ('localhost', '127.0.0.1', '0.0.0.0', '::1'):
                    raise ValueError("Cannot auto-follow localhost URLs for security")
                    
                return WebPath(value).get()
            return value
        elif isinstance(data, list):
            try:
                idx = int(key)
                value = data[idx]
                if isinstance(value, str) and value.startswith(('http://', 'https://')):
                    return WebPath(value).get()
                return value
            except (ValueError, IndexError):
                pass
        raise KeyError(f"Key '{key}' not found in response")
    
    def __getitem__(self, key):
        data = self.json_data
        if isinstance(data, dict):
            return data[key]
        elif isinstance(data, list):
            return data[key]
        raise TypeError("Response data is not subscriptable")
    
    def __contains__(self, key):
        data = self.json_data
        return key in data if isinstance(data, dict) else False
    
    def get(self, key, default=None):
        data = self.json_data
        if isinstance(data, dict):
            return data.get(key, default)
        return default
    
    def keys(self):
        data = self.json_data
        return data.keys() if isinstance(data, dict) else []
    
    def values(self):
        data = self.json_data
        return data.values() if isinstance(data, dict) else []

    def items(self):
        data = self.json_data
        return data.items() if isinstance(data, dict) else []
    
    def inspect(self):
        console = Console()
        
        status_color = "green" if 200 <= self.status_code < 300 else "red" if self.status_code >= 400 else "yellow"
        status_text = f"[{status_color}]{self.status_code}[/{status_color}] {getattr(self._response, 'reason', 'OK')}"
        
        elapsed = getattr(self._response, 'elapsed', None)
        time_text = f"{int(elapsed.total_seconds() * 1000)}ms" if elapsed else "unknown"
        
        size_text = f"{len(self.content):,} bytes"
        
        status_info = f"{status_text} • {time_text} • {size_text}"
        console.print(Panel(status_info, title="Response", border_style="blue"))
        
        self._print_response_body(console)
        
        self._print_headers(console)

    def _print_response_body(self, console):
        content_type = self.headers.get('content-type', '').lower()
        
        if 'json' in content_type:
            try:
                json_text = json.dumps(self.json_data, indent=2)
                syntax = Syntax(json_text, "json", theme="monokai", line_numbers=False)
                console.print(Panel(syntax, title="Response Body", border_style="green"))
            except:
                console.print(Panel(self.text[:1000] + "..." if len(self.text) > 1000 else self.text, 
                                title="Response Body", border_style="yellow"))
        elif 'text' in content_type or 'html' in content_type:
            preview = self.text[:500] + "..." if len(self.text) > 500 else self.text
            console.print(Panel(preview, title="Response Body", border_style="green"))
        else:
            console.print(Panel(f"Binary content ({len(self.content)} bytes)", 
                            title="Response Body", border_style="yellow"))

    def _print_headers(self, console):
        table = Table(show_header=True, header_style="bold blue", box=box.SIMPLE)
        table.add_column("Header", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")
        
        for key, value in self.headers.items():
            table.add_row(key, value)
        
        console.print(Panel(table, title="Headers", border_style="blue"))

    def curl(self):
        url = str(self.url)
        method = "GET"
        
        curl_cmd = f"curl -X {method} '{url}'"
        
        request_headers = ['Authorization', 'Content-Type', 'User-Agent', 'Accept']
        for header in request_headers:
            if header in self.headers:
                curl_cmd += f" \\\n  -H '{header}: {self.headers[header]}'"
        
        console = Console()
        syntax = Syntax(curl_cmd, "bash", theme="monokai")
        console.print(Panel(syntax, title="cURL Command", border_style="green"))
        
        return curl_cmd

    def paginate(self, max_pages=100, next_key=None):
        current_page = self
        page_count = 0
        visited_urls = set()
        
        while current_page and page_count < max_pages:
            current_url = str(current_page.url)
            
            if current_url in visited_urls:
                break
            visited_urls.add(current_url)
            
            yield current_page
            page_count += 1
            
            if next_key:
                next_url = self._extract_nested_value(current_page.json_data, next_key)
            else:
                next_url = self._find_next_url(current_page)
                
            if not next_url or not isinstance(next_url, str):
                break
                
            try:
                from .core import WebPath
                current_page = WebPath(next_url).get()
            except Exception:
                break

    def _find_next_url(self, page):
        data = page.json_data
        if not isinstance(data, dict):
            return None
        
        patterns = [
            'next',
            'next_url',
            'nextUrl',
            'next_page',
            'links.next',
            'pagination.next',
            '_links.next.href',
        ]
        
        for pattern in patterns:
            next_url = self._extract_nested_value(data, pattern)
            if next_url and isinstance(next_url, str) and next_url.startswith(('http://', 'https://')):
                return next_url
        
        return None

    def _extract_nested_value(self, data, path):
        try:
            parts = path.split('.')
            current = data
            for part in parts:
                current = current[part]
            return current
        except (KeyError, TypeError):
            return None

    def paginate_all(self, max_pages=100, next_key=None, data_key=None):
        all_results = []
        for page in self.paginate(max_pages=max_pages, next_key=next_key):
            page_data = page.json_data
            
            if data_key:
                items = self._extract_nested_value(page_data, data_key)
                if isinstance(items, list):
                    all_results.extend(items)
                elif items is not None:
                    all_results.append(items)
            else:
                if isinstance(page_data, list):
                    all_results.extend(page_data)
                elif isinstance(page_data, dict):
                    for key in ['data', 'results', 'items', 'records', 'content']:
                        if key in page_data and isinstance(page_data[key], list):
                            all_results.extend(page_data[key])
                            break
                    else:
                        all_results.append(page_data)
        
        return all_results

    def paginate_items(self, item_key='data', max_pages=100):
        all_items = []
        for page in self.paginate(max_pages=max_pages):
            page_data = page.json_data
            if isinstance(page_data, dict) and item_key in page_data:
                items = page_data[item_key]
                if isinstance(items, list):
                    all_items.extend(items)
                else:
                    all_items.append(items)
        return all_items

def _build_retry_adapter(retries: int, backoff: float) -> HTTPAdapter:
    retry_cfg = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=(502, 503, 504),
        allowed_methods=[v.upper() for v in _HTTP_VERBS],
        raise_on_redirect=False,
        raise_on_status=False,
    )
    return HTTPAdapter(max_retries=retry_cfg)

def http_request(verb: str, url, *a: Any, retries: int | None = None, backoff: float = 0.3, **kw: Any):
    cache_config = None
    if hasattr(url, '_cache_config'):
        cache_config = url._cache_config
    
    if hasattr(url, 'scheme'):
        url_str = str(url)
        scheme = url.scheme
    else:
        url_str = url
        scheme = urlsplit(url).scheme
    
    if scheme not in _HTTP_SCHEMES:
        raise ValueError(f"{verb.upper()} only valid for http/https URLs")

    if cache_config:
        cached = cache_config.get(verb, url_str)
        if cached:
            return WebResponse(CachedResponse(cached), url)

    try:
        if retries:
            adapter = _build_retry_adapter(retries, backoff)
            with requests.Session() as sess:
                sess.mount("http://", adapter)
                sess.mount("https://", adapter)
                func = getattr(sess, verb)
                resp = func(str(url), *a, **kw)
                for _ in range(retries - 1):
                    if resp.status_code not in (502, 503, 504):
                        break
                    resp = func(str(url), *a, **kw)
        else:
            resp = getattr(requests, verb)(str(url), *a, **kw)
            
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"Failed to connect to {url_str}")
    except requests.exceptions.Timeout:
        raise TimeoutError(f"Request to {url_str} timed out")

    if 400 <= resp.status_code < 600:
        error_msg = _get_helpful_error_message(resp, url_str)
        raise requests.HTTPError(error_msg)

    if cache_config and 200 <= resp.status_code < 300:
        cache_config.set(verb, url_str, resp)
    
    if hasattr(url, '_rate_limit') and url._rate_limit:
        import time
        min_interval = 1.0 / url._rate_limit
        elapsed = time.time() - getattr(url, '_last_request_time', 0)
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        url._last_request_time = time.time()


    if hasattr(url, '_enable_logging') and url._enable_logging:
        console = Console()
        elapsed = getattr(resp, 'elapsed', None)
        elapsed_ms = int(elapsed.total_seconds() * 1000) if elapsed else 0
        status_color = "green" if 200 <= resp.status_code < 300 else "red" if resp.status_code >= 400 else "yellow"
        console.print(f"{verb.upper()} {url_str} → [{status_color}]{resp.status_code}[/{status_color}] ({elapsed_ms}ms)")

    return WebResponse(resp, url)

def _get_helpful_error_message(response, url):
    hostname = urlsplit(url).hostname
    status = response.status_code
    
    error_details = ""
    try:
        data = response.json()
        for key in ['error', 'message', 'error_description', 'detail']:
            if key in data:
                error_details = f" - {data[key]}"
                break
    except Exception:
        pass
    
    if status == 401:
        return f"Authentication failed for {hostname}{error_details}. Check your API credentials."
    elif status == 403:
        return f"Access forbidden to {hostname}{error_details}. Check permissions or account status."
    elif status == 404:
        return f"Endpoint not found: {url}{error_details}"
    elif status == 429:
        retry_after = response.headers.get('Retry-After', 'unknown')
        return f"Rate limited by {hostname}. Retry after {retry_after} seconds{error_details}"
    elif status >= 500:
        return f"Server error on {hostname}{error_details}. Try again later."
    
    return f"HTTP {status} from {hostname}{error_details}"

@contextlib.contextmanager
def session_cm(url, **sess_kw):
    s = requests.Session(**sess_kw)
    try:
        yield lambda verb, *a, **kw: WebResponse(getattr(s, verb)(str(url), *a, **kw), url)
    finally:
        s.close()

async def aget_async(url, *a, **kw):
    client = _client_cv.get()
    if client is None:
        client = httpx.AsyncClient()
        _client_cv.set(client)

    resp = await client.get(str(url), *a, **kw)
    return WebResponse(resp, url) 

def _close_async_client():
    client = _client_cv.get(None)
    if client and not client.is_closed:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(client.aclose())
atexit.register(_close_async_client)