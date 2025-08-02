from __future__ import annotations
import time
import logging
from urllib.parse import urlsplit
import httpx
import json
import jmespath
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.panel import Panel
from rich import box
import asyncio

_HTTP_SCHEMES = ("http", "https")

class CachedResponse:
    def __init__(self, cached_data):
        self.status_code = cached_data['status_code']
        self.headers = cached_data['headers']
        self.content = cached_data['content'].encode('utf-8')
        self.text = cached_data['content']
        self.url = cached_data['url']
    
    def json(self):
        return json.loads(self.content)
    
    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise httpx.HTTPStatusError(f"{self.status_code} Client Error", request=None, response=self)
        
class WebResponse:
    def __init__(self, response, parent_path):
        self._response = response
        self._parent = parent_path
        self._json_data = None
    
    def __getattr__(self, name):
        return getattr(self._response, name)
    
    def iter_content(self, chunk_size=8192):
        if hasattr(self._response, 'iter_bytes'):
            yield from self._response.iter_bytes(chunk_size=chunk_size)
        elif hasattr(self._response, 'iter_content'):
            yield from self._response.iter_content(chunk_size=chunk_size)
        else:
            content = self.content
            for i in range(0, len(content), chunk_size):
                yield content[i:i+chunk_size]
    
    def find(self, expression, default=None):
        data = self.json_data
        
        if ' || ' in expression:
            parts = expression.split(' || ')
            expressions = []
            for part in parts:
                expressions.append(part.strip())

            for expr in expressions:
                result = jmespath.search(expr, data)
                if result is not None:
                    return result
            return default
        else:
            result = jmespath.search(expression, data)
            if result is not None:
                return result
            return default

    def find_all(self, expression):
        result = self.find(expression, default=[])
        if not result:
            return []
        if isinstance(result, list):
            return result
        return [result]


    def extract(self, *expressions, flatten=False):
        if len(expressions) == 1:
            result = self.find(expressions[0])
            if flatten and isinstance(result, list):
                return result
            return result
        
        results = []
        for expr in expressions:
            result = self.find(expr)
            if flatten and isinstance(result, list):
                results.extend(result)
            else:
                results.append(result)
        
        return tuple(results)

    def has_path(self, expression):
        sentinel = object()
        result = self.find(expression, default=sentinel)
        return result is not sentinel

    def get_pagination_info(self):
        return {
            'next': self.find("next || next_url || pagination.next"),
            'prev': self.find("prev || prev_url || pagination.prev"), 
            'total': self.find("total || count || pagination.total"),
            'page': self.find("page || pagination.page"),
            'per_page': self.find("per_page || limit || pagination.per_page || pagination.limit")
        }
    
    @property
    def json_data(self):
        if self._json_data is None:
            self._json_data = self._response.json()
        return self._json_data

    def json(self):
        return self._response.json()
        
    def __truediv__(self, key):
        data = self.json_data
        
        if isinstance(data, dict):
            value = data[key]
            if isinstance(value, str) and value.startswith(('http://', 'https://')):
                from webpath.core import WebPath
                return WebPath(value).get()
            return value
        elif isinstance(data, list):
            idx = int(key)
            value = data[idx]
            if isinstance(value, str) and value.startswith(('http://', 'https://')):
                from webpath.core import WebPath
                return WebPath(value).get()
            return value
    
    def __getitem__(self, key):
        data = self.json_data
        if isinstance(data, dict):
            return data[key]
        elif isinstance(data, list):
            return data[key]
        raise TypeError("Response data is not subscriptable")
    
    def __contains__(self, key):
        data = self.json_data
        if not isinstance(data, dict):
            return False
        return key in data
    
    def get(self, key, default=None):
        data = self.json_data
        if isinstance(data, dict):
            return data.get(key, default)
        return default
    
    def keys(self):
        data = self.json_data
        if isinstance(data, dict):
            return data.keys()
        return []

        
    def values(self):
        data = self.json_data
        if isinstance(data, dict):
            return data.values()
        return []

    def items(self):
        data = self.json_data
        if isinstance(data, dict):
            return data.items()
        return []
    
    def inspect(self, logger=None):
        if self.status_code >= 400:
            status_color = "red"
        elif self.status_code >= 200:
            status_color = "green" 
        else:
            status_color = "yellow"

        status_text = f"{self.status_code} {getattr(self._response, 'reason_phrase', 'OK')}"
        
        elapsed = getattr(self._response, 'elapsed', None)
        if elapsed:
            time_text = f"{int(elapsed.total_seconds() * 1000)}ms"
        else:
            time_text = "unknown"

        size_text = f"{len(self.content):,} bytes"
        
        if logger:
            status_info = f"Response: {status_text} | Elapsed: {time_text} | Size: {size_text}"
            
            headers_str = ""
            for k, v in self.headers.items():
                headers_str += f"  {k}: {v}\n"
            headers_str = headers_str.rstrip()
            
            content_type = self.headers.get('content-type', '').lower()
            def truncate_text(text, limit=500):
                if len(text) > limit:
                    return text[:limit] + "..."
                return text

            if 'json' in content_type:
                try:
                    body_preview = json.dumps(self.json_data, indent=2)
                    body_preview = truncate_text(body_preview, 1000)
                except Exception:
                    body_preview = truncate_text(self.text)
            else:
                body_preview = truncate_text(self.text)

            logger.info(f"HTTP Response Inspection:\n{status_info}")
            logger.info(f"Headers:\n{headers_str}")
            logger.info(f"Body Preview:\n{body_preview}")
        else:
            console = Console()
            
            status_info = f"[{status_color}]{status_text}[/{status_color}] * {time_text} * {size_text}"
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
                text = self.text[:1000]
                if len(self.text) > 1000:
                    text += "..."
                console.print(Panel(text, title="Response Body", border_style="yellow"))
        elif 'text' in content_type or 'html' in content_type:
            text = self.text[:500]
            if len(self.text) > 500:
                text += "..."
            console.print(Panel(text, title="Response Body", border_style="green"))
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
        
        while current_page and page_count < max_pages:
            yield current_page
            page_count += 1
            
            if next_key:
                next_url = current_page.find(next_key)
            else:
                next_url = current_page.find("next || next_url || pagination.next")
                
            if not next_url:
                break
            
            from webpath.core import WebPath
            current_page = WebPath(next_url).get()

    def paginate_all(self, max_pages=100, next_key=None, data_key=None):
        all_results = []
        for page in self.paginate(max_pages=max_pages, next_key=next_key):
            page_data = page.json_data
            
            if data_key:
                items = page.find(data_key)
                if isinstance(items, list):
                    all_results.extend(items)
                elif items is not None:
                    all_results.append(items)
            else:
                if isinstance(page_data, list):
                    all_results.extend(page_data)
                elif isinstance(page_data, dict):
                    items = page.find("data || results || items || records || content")
                    if isinstance(items, list):
                        all_results.extend(items)
                    else:
                        all_results.append(page_data)
        
        return all_results

    def paginate_items(self, item_key='data', max_pages=100):
        all_items = []
        for page in self.paginate(max_pages=max_pages):
            items = page.find(item_key)
            if isinstance(items, list):
                all_items.extend(items)
            elif items is not None:
                all_items.append(items)
        return all_items

def _sync_http_request(verb, url, *a, client=None, retries=None, **kw):
    cache_config = getattr(url, '_cache_config', None)
    
    url_str = str(url)
    scheme = getattr(url, 'scheme', urlsplit(url_str).scheme)
    
    if scheme not in _HTTP_SCHEMES:
        raise ValueError(f"{verb.upper()} only valid for http/https URLs")

    is_streaming = kw.pop('stream', False)

    if cache_config and not is_streaming:
        cached = cache_config.get(verb, url_str)
        if cached:
            return WebResponse(CachedResponse(cached), url)

    if client:
        if is_streaming:
            resp = client.stream(verb.upper(), url_str, **kw)
            resp = resp.__enter__()
        else:
            resp = getattr(client, verb)(url_str, **kw)
    elif retries:
        transport = httpx.HTTPTransport(retries=retries)
        with httpx.Client(transport=transport) as temp_client:
            if is_streaming:
                resp = temp_client.stream(verb.upper(), url_str, **kw)
                resp = resp.__enter__()
            else:
                resp = getattr(temp_client, verb)(url_str, *a, **kw)
    else:
        with httpx.Client() as temp_client:
            if is_streaming:
                resp = temp_client.stream(verb.upper(), url_str, **kw)
                resp = resp.__enter__()
            else:
                resp = getattr(temp_client, verb)(url_str, *a, **kw)

    if 400 <= resp.status_code < 600:
        error_msg = _get_helpful_error_message(resp, url_str)
        raise httpx.HTTPStatusError(error_msg, request=resp.request, response=resp)

    if cache_config and not is_streaming and resp.status_code >= 200 and resp.status_code < 300:
        cache_config.set(verb, url_str, resp)
    
    _handle_rate_limit(url)
    _handle_logging(verb, url_str, resp, url)

    return WebResponse(resp, url)

async def _async_http_request(verb, url, *a, client=None, retries=None, **kw):
    cache_config = getattr(url, '_cache_config', None)
    
    url_str = str(url)
    scheme = getattr(url, 'scheme', urlsplit(url_str).scheme)
    
    if scheme not in _HTTP_SCHEMES:
        raise ValueError(f"{verb.upper()} only valid for http/https URLs")

    if cache_config:
        cached = cache_config.get(verb, url_str)
        if cached:
            return WebResponse(CachedResponse(cached), url)

    if client:
        resp = await getattr(client, verb)(url_str, **kw)
    elif retries:
        transport = httpx.AsyncHTTPTransport(retries=retries)
        async with httpx.AsyncClient(transport=transport) as temp_client:
            resp = await getattr(temp_client, verb)(url_str, *a, **kw)
    else:
        async with httpx.AsyncClient() as temp_client:
            resp = await getattr(temp_client, verb)(url_str, *a, **kw)

    if 400 <= resp.status_code < 600:
        error_msg = _get_helpful_error_message(resp, url_str)
        raise httpx.HTTPStatusError(error_msg, request=resp.request, response=resp)

    if cache_config and 200 <= resp.status_code < 300:
        cache_config.set(verb, url_str, resp)
    
    await _handle_rate_limit_async(url)

    _handle_logging(verb, url_str, resp, url)

    return WebResponse(resp, url)

def _handle_rate_limit(url):
    if not getattr(url, '_rate_limit', None):
        return
    
    interval = 1.0 / url._rate_limit
    elapsed = time.time() - getattr(url, '_last_request_time', 0)
    if elapsed < interval:
        time.sleep(interval - elapsed)
    url._last_request_time = time.time()

async def _handle_rate_limit_async(url):
    if hasattr(url, '_rate_limit') and url._rate_limit:
        min_interval = 1.0 / url._rate_limit
        elapsed = time.time() - getattr(url, '_last_request_time', 0)
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        url._last_request_time = time.time()

def _handle_logging(verb, url_str, resp, url_obj):
    logger = getattr(url_obj, '_enable_logging', False)
    if logger:
        try:
            elapsed_ms = int(resp.elapsed.total_seconds() * 1000)
        except AttributeError:
            elapsed_ms = 0

        log_message = f"{verb.upper()} {url_str} -> {resp.status_code} ({elapsed_ms}ms)"

        if isinstance(logger, logging.Logger):
            if 200 <= resp.status_code < 300:
                logger.info(log_message)
            elif resp.status_code >= 400:
                logger.warning(log_message)
            else:
                logger.info(log_message)
        else:

            if resp.status_code >= 200 and resp.status_code < 300:
                status_color = "green"
            elif resp.status_code >= 400:
                status_color = "red"
            else:
                status_color = "yellow"

            console = Console()
            console.print(f"{verb.upper()} {url_str} -> [{status_color}]{resp.status_code}[/{status_color}] ({elapsed_ms}ms)")

def _get_helpful_error_message(response, url):
    hostname = urlsplit(url).hostname
    status = response.status_code
    
    if status == 401:
        return f"Auth failed for {hostname}"
    elif status == 403:
        return f"Forbidden: {hostname}"
    elif status == 404:
        return f"Not found: {url}"
    elif status >= 500:
        return f"Server error: {hostname}"
    
    return f"HTTP {status} from {hostname}"

def http_request(verb, url, *args, **kwargs):
    return _sync_http_request(verb, url, *args, **kwargs)

async def async_http_request(verb, url, *args, **kwargs):
    return await _async_http_request(verb, url, *args, **kwargs)