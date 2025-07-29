import pytest
import json
import httpx
from unittest.mock import Mock, patch, MagicMock
from webpath._http import (
    WebResponse, CachedResponse, _sync_http_request, _async_http_request,
    _handle_rate_limit, _handle_logging, _get_helpful_error_message
)


class TestCachedResponse:
    def test_cached_response_init(self):
        cached_data = {
            'status_code': 200,
            'headers': {'Content-Type': 'application/json'},
            'content': '{"test": "data"}',
            'url': 'https://api.example.com/test'
        }
        
        resp = CachedResponse(cached_data)
        
        assert resp.status_code == 200
        assert resp.headers == {'Content-Type': 'application/json'}
        assert resp.text == '{"test": "data"}'
        assert resp.content == b'{"test": "data"}'
        assert resp.url == 'https://api.example.com/test'

    def test_cached_response_json(self):
        cached_data = {
            'status_code': 200,
            'headers': {},
            'content': '{"name": "test", "value": 123}',
            'url': 'https://api.example.com'
        }
        
        resp = CachedResponse(cached_data)
        data = resp.json()
        
        assert data == {"name": "test", "value": 123}

    def test_cached_response_raise_for_status_success(self):
        cached_data = {
            'status_code': 200,
            'headers': {},
            'content': '{}',
            'url': 'https://api.example.com'
        }
        
        resp = CachedResponse(cached_data)
        resp.raise_for_status()

    def test_cached_response_raise_for_status_error(self):
        cached_data = {
            'status_code': 404,
            'headers': {},
            'content': '{}',
            'url': 'https://api.example.com'
        }
        
        resp = CachedResponse(cached_data)
        
        with pytest.raises(httpx.HTTPStatusError):
            resp.raise_for_status()


class TestWebResponse:
    @pytest.fixture
    def mock_response(self):
        response = Mock()
        response.status_code = 200
        response.headers = {'Content-Type': 'application/json'}
        response.json.return_value = {
            "id": 123,
            "name": "test item",
            "data": [{"id": 1}, {"id": 2}],
            "pagination": {
                "next": "https://api.example.com/page2",
                "total": 50
            }
        }
        response.content = b'{"test": "data"}'
        response.text = '{"test": "data"}'
        response.url = "https://api.example.com/test"
        return response

    @pytest.fixture
    def web_response(self, mock_response):
        return WebResponse(mock_response, Mock())

    def test_find_basic(self, web_response):
        result = web_response.find("name")
        assert result == "test item"
        
        result = web_response.find("nonexistent")
        assert result is None
        
        result = web_response.find("nonexistent", "default")
        assert result == "default"

    def test_find_nested(self, web_response):
        result = web_response.find("pagination.next")
        assert result == "https://api.example.com/page2"

    def test_find_all(self, web_response):
        result = web_response.find_all("data[*].id")
        assert result == [1, 2]
        
        result = web_response.find_all("nonexistent")
        assert result == []

    def test_extract_single(self, web_response):
        result = web_response.extract("name")
        assert result == "test item"

    def test_extract_multiple(self, web_response):
        result = web_response.extract("name", "id")
        assert result == ("test item", 123)

    def test_extract_flatten(self, web_response):
        result = web_response.extract("data[*].id", flatten=True)
        assert result == [1, 2]

    def test_has_path(self, web_response):
        assert web_response.has_path("name") is True
        assert web_response.has_path("nonexistent") is False

    def test_get_errors(self, web_response):
        web_response._response.json.return_value = {"error": "Something went wrong"}
        web_response._json_data = None
        
        result = web_response.get_errors()
        assert result == "Something went wrong"

    def test_get_ids(self, web_response):
        result = web_response.get_ids()
        assert result == 123

    def test_get_pagination_info(self, web_response):
        web_response._json_data = None
        
        info = web_response.get_pagination_info()
        assert info['next'] == "https://api.example.com/page2"
        assert info['total'] == 50
        assert info['page'] is None

    def test_dict_like_access(self, web_response):
        assert web_response["name"] == "test item"
        assert web_response.get("name") == "test item"
        assert web_response.get("nonexistent", "default") == "default"
        assert "name" in web_response
        assert "nonexistent" not in web_response

    def test_truediv_dict_access(self, web_response):
        result = web_response / "name"
        assert result == "test item"

    def test_truediv_list_access(self, web_response):
        web_response._response.json.return_value = ["item1", "item2", "item3"]
        web_response._json_data = None
        
        result = web_response / "1"
        assert result == "item2"

    @patch('webpath.core.WebPath') 
    def test_truediv_url_following(self, mock_webpath, web_response):
        web_response._response.json.return_value = {
            "next_url": "https://api.example.com/next"
        }
        web_response._json_data = None
        
        mock_path_instance = Mock()
        mock_webpath.return_value = mock_path_instance
        
        result = web_response / "next_url"
        
        mock_webpath.assert_called_once_with("https://api.example.com/next")
        mock_path_instance.get.assert_called_once()

    @patch('webpath.core.WebPath')
    def test_paginate(self, mock_webpath, web_response):
        web_response._response.json.return_value = {
            "id": 123,
            "name": "test item", 
            "data": [{"id": 1}, {"id": 2}],
        }
        web_response._json_data = None
        
        pages = list(web_response.paginate(max_pages=2))
        
        assert len(pages) == 1
        assert pages[0] == web_response

    def test_paginate_all_simple(self, web_response):
        web_response._response.json.return_value = {
            "id": 123,
            "name": "test item", 
            "data": [{"id": 1}, {"id": 2}]
        }
        web_response._json_data = None
        
        result = web_response.paginate_all(data_key="data")
        assert result == [{"id": 1}, {"id": 2}]


class TestHttpRequests:
    @pytest.fixture
    def mock_url(self):
        url = Mock()
        url.__str__ = lambda self: "https://api.example.com/test" 
        url.scheme = "https"
        url._cache_config = None
        url._rate_limit = None
        url._enable_logging = False
        url._last_request_time = 0.0
        return url

    @patch('webpath._http.urlsplit') 
    @patch('httpx.Client')
    def test_sync_http_request_basic(self, mock_client_class, mock_urlsplit, mock_url):
        mock_split = Mock()
        mock_split.scheme = "https"
        mock_urlsplit.return_value = mock_split
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        result = _sync_http_request("get", mock_url)
        
        assert isinstance(result, WebResponse)
        mock_client.get.assert_called_once_with("https://api.example.com/test")

    @patch('webpath._http.urlsplit')
    @patch('httpx.Client')
    def test_sync_http_request_with_client(self, mock_client_class, mock_urlsplit, mock_url):
        mock_split = Mock()
        mock_split.scheme = "https"
        mock_urlsplit.return_value = mock_split
        
        provided_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        
        provided_client.get.return_value = mock_response
        
        result = _sync_http_request("get", mock_url, client=provided_client)
        
        provided_client.get.assert_called_once_with("https://api.example.com/test")

    @patch('webpath._http.urlsplit') 
    def test_sync_http_request_invalid_scheme(self, mock_urlsplit, mock_url):
        mock_url.scheme = "ftp"
        
        with pytest.raises(ValueError, match="GET only valid for http/https URLs"):
            _sync_http_request("get", mock_url)

    @patch('webpath._http.urlsplit')
    @patch('httpx.Client')
    def test_sync_http_request_error_response(self, mock_client_class, mock_urlsplit, mock_url):
        mock_split = Mock()
        mock_split.scheme = "https"
        mock_urlsplit.return_value = mock_split
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.request = Mock()
        
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        with patch('webpath._http._get_helpful_error_message') as mock_error_msg:
            mock_error_msg.return_value = "Not found"
            
            with pytest.raises(httpx.HTTPStatusError):
                _sync_http_request("get", mock_url)

    @pytest.mark.asyncio
    @patch('webpath._http.urlsplit')
    @patch('httpx.AsyncClient')
    async def test_async_http_request_basic(self, mock_client_class, mock_urlsplit, mock_url):
        mock_split = Mock()
        mock_split.scheme = "https"
        mock_urlsplit.return_value = mock_split
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        
        async def async_get(*args, **kwargs):
            return mock_response
            
        mock_client.get = async_get
        
        async def mock_aenter(self):
            return mock_client
        async def mock_aexit(self, exc_type, exc_val, exc_tb):
            pass
            
        mock_client_instance = Mock()
        mock_client_instance.__aenter__ = mock_aenter
        mock_client_instance.__aexit__ = mock_aexit
        mock_client_class.return_value = mock_client_instance
        
        result = await _async_http_request("get", mock_url)
        
        assert isinstance(result, WebResponse)

    def test_handle_rate_limit_no_limit(self, mock_url):
        mock_url._rate_limit = None
        
        _handle_rate_limit(mock_url)

    @patch('time.time')
    @patch('time.sleep')
    def test_handle_rate_limit_with_limit(self, mock_sleep, mock_time, mock_url):
        mock_url._rate_limit = 2.0  
        mock_url._last_request_time = 10.0
        mock_time.return_value = 10.3 
        
        _handle_rate_limit(mock_url)
        
        mock_sleep.assert_called_once()
        sleep_time = mock_sleep.call_args[0][0]
        assert abs(sleep_time - 0.2) < 0.0001

    @patch('webpath._http.Console')
    def test_handle_logging_enabled(self, mock_console_class, mock_url):
        mock_url._enable_logging = True
        mock_console = Mock()
        mock_console_class.return_value = mock_console
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.150
        
        _handle_logging("get", "https://api.example.com", mock_response, mock_url)
        
        mock_console.print.assert_called_once()

    def test_get_helpful_error_message_401(self):
        response = Mock()
        response.status_code = 401
        
        msg = _get_helpful_error_message(response, "https://api.example.com/test")
        assert msg == "Auth failed for api.example.com"

    def test_get_helpful_error_message_404(self):
        response = Mock()
        response.status_code = 404
        
        msg = _get_helpful_error_message(response, "https://api.example.com/test")
        assert msg == "Not found: https://api.example.com/test"

    def test_get_helpful_error_message_500(self):
        response = Mock()
        response.status_code = 500
        
        msg = _get_helpful_error_message(response, "https://api.example.com/test")
        assert msg == "Server error: api.example.com"

    def test_get_helpful_error_message_generic(self):
        response = Mock()
        response.status_code = 418
        
        msg = _get_helpful_error_message(response, "https://api.example.com/test")
        assert msg == "HTTP 418 from api.example.com"


class TestInspectAndCurl:
    @pytest.fixture
    def web_response_with_data(self):
        response = Mock()
        response.status_code = 200
        response.headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer token123'
        }
        response.json.return_value = {"test": "data"}
        response.content = b'{"test": "data"}'
        response.text = '{"test": "data"}'
        response.url = "https://api.example.com/test"
        
        elapsed_mock = Mock()
        elapsed_mock.total_seconds.return_value = 0.150
        response.elapsed = elapsed_mock
        
        return WebResponse(response, Mock())

    @patch('webpath._http.Console')
    def test_inspect_method(self, mock_console_class, web_response_with_data):
        mock_console = Mock()
        mock_console_class.return_value = mock_console
        
        web_response_with_data.inspect()
        
        assert mock_console.print.call_count >= 3

    @patch('webpath._http.Console')
    def test_curl_method(self, mock_console_class, web_response_with_data):
        mock_console = Mock()
        mock_console_class.return_value = mock_console
        
        result = web_response_with_data.curl()
        
        assert "curl -X GET" in result
        assert "https://api.example.com/test" in result
        mock_console.print.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])