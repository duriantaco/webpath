import pytest
import httpx
from unittest.mock import Mock, patch
from webpath.core import WebPath, Client, _idna

class TestIdnaFunction:
    def test_idna_ascii(self):
        result = _idna("example.com")
        assert result == "example.com"
    
    def test_idna_unicode(self):
        result = _idna("münchen.de")
        assert result == "xn--mnchen-3ya.de"
    
    def test_idna_unicode_error(self):
        class FailingString(str):
            def encode(self, *args, **kwargs):
                raise UnicodeError("Test error")
        
        failing_netloc = FailingString("test.com")
        result = _idna(failing_netloc)
        assert result == "test.com"

class TestWebPathBasics:
    def test_init_and_str(self):
        path = WebPath("https://api.example.com/users")
        assert str(path) == "https://api.example.com/users"

    def test_repr(self):
        path = WebPath("https://api.example.com")
        assert repr(path) == "WebPath('https://api.example.com')"

    def test_equality(self):
        path1 = WebPath("https://api.example.com")
        path2 = WebPath("https://api.example.com")
        path3 = WebPath("https://different.com")
        
        assert path1 == path2
        assert path1 == "https://api.example.com"
        assert path1 != path3
        assert path1 != "https://different.com"

    def test_hash(self):
        path1 = WebPath("https://api.example.com")
        path2 = WebPath("https://api.example.com")
        assert hash(path1) == hash(path2)

    def test_bool(self):
        assert bool(WebPath("https://api.example.com")) is True
        assert bool(WebPath("")) is False

    def test_url_properties(self):
        path = WebPath("https://user:pass@api.example.com:8080/users/123?active=true#top")
        
        assert path.scheme == "https"
        assert path.netloc == "user:pass@api.example.com:8080"
        assert path.host == "api.example.com"
        assert path.port == "8080"
        assert path.path == "/users/123"
        assert path.name == "123"

    def test_port_none_when_missing(self):
        path = WebPath("https://api.example.com/users")
        assert path.port is None

    def test_suffix(self):
        path = WebPath("https://api.example.com/file.json")
        assert path.suffix == ".json"
        
        path_no_suffix = WebPath("https://api.example.com/users")
        assert path_no_suffix.suffix == ""

    def test_query_property_simple(self):
        path = WebPath("https://api.example.com?name=test&active=true")
        query = path.query
        
        assert query["name"] == "test"
        assert query["active"] == "true"

    def test_query_property_multiple_values(self):
        path = WebPath("https://api.example.com?tags=a&tags=b")
        query = path.query
        
        assert query["tags"] == "b"

    def test_iter_path_segments(self):
        path = WebPath("https://api.example.com/users/123/posts")
        segments = list(path)
        assert segments == ["users", "123", "posts"]

    def test_ensure_trailing_slash(self):
        path = WebPath("https://api.example.com/users")
        with_slash = path.ensure_trailing_slash()
        assert str(with_slash) == "https://api.example.com/users/"
        
        path_with_slash = WebPath("https://api.example.com/users/")
        result = path_with_slash.ensure_trailing_slash()
        assert str(result) == "https://api.example.com/users/"

    def test_initialization_sets_defaults(self):
        path = WebPath("https://api.example.com")
        
        assert path._url == "https://api.example.com"
        assert path._cache == {}
        assert path._cache_config is None
        assert path._allow_auto_follow is False
        assert path._enable_logging is False
        assert path._rate_limit is None
        assert path._last_request_time == 0
        assert path._default_headers == {}
        assert path._retries is None
        assert path._backoff == 0.3
        assert path._jitter == 0.0
        assert path._timeout is None
        assert path._sync_client is None
        assert path._async_client is None

class TestWebPathHttpMethods:
    @patch('webpath.core._sync_http_request')
    def test_get_method(self, mock_sync_request):
        mock_response = Mock()
        mock_sync_request.return_value = mock_response
        
        path = WebPath("https://api.example.com")
        result = path.get()
        
        args, kwargs = mock_sync_request.call_args
        assert args[0] == "get"
        assert args[1] == path
        assert result == mock_response

    @patch('webpath.core._sync_http_request')
    def test_post_method(self, mock_sync_request):
        mock_response = Mock()
        mock_sync_request.return_value = mock_response
        
        path = WebPath("https://api.example.com")
        
        args, kwargs = mock_sync_request.call_args
        assert args[0] == "post"
        assert args[1] == path
        assert kwargs["json"] == {"test": "data"}

    @pytest.mark.asyncio
    @patch('webpath.core._async_http_request')
    async def test_async_get_method(self, mock_async_request):
        mock_response = Mock()
        mock_async_request.return_value = mock_response
        
        path = WebPath("https://api.example.com")
        result = await path.aget()
        
        args, kwargs = mock_async_request.call_args
        assert args[0] == "get"
        assert args[1] == path
        assert result == mock_response

    def test_invalid_method_raises_error(self):
        path = WebPath("https://api.example.com")
        
        with pytest.raises(AttributeError, match="'WebPath' object has no attribute 'invalid_method'"):
            _ = path.invalid_method

class TestWebPathOtherMethods:
    @patch('httpx.Client')
    def test_session(self, mock_client_class):
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        path = WebPath("https://api.example.com")
        result = path.session(timeout=30)
        
        mock_client_class.assert_called_once_with(timeout=30)
        assert result == mock_client

    @patch('webpath.core.download_file')
    def test_download_basic(self, mock_download):
        path = WebPath("https://api.example.com/file.zip")
        path.download("/tmp/file.zip")
        
        mock_download.assert_called_once_with(path, "/tmp/file.zip", backoff=0.3)

    @patch('webpath.core.download_file')
    def test_download_with_retries_set(self, mock_download):
        path = WebPath("https://api.example.com/file.zip")
        path._retries = 3
        
        path.download("/tmp/file.zip", chunk_size=1024)
        
        mock_download.assert_called_once_with(
            path, "/tmp/file.zip", 
            retries=3, backoff=0.3, chunk_size=1024
        )

    def test_memo_caching(self):
        path = WebPath("https://api.example.com?test=1&test=2")
        
        query1 = path.query
        query2 = path.query
        
        assert query1 is query2

    def test_url_parts_access(self):
        path = WebPath("https://user:pass@example.com:8080/path?query=1#frag")
        
        parts = path._parts
        assert parts.scheme == "https"
        assert parts.netloc == "user:pass@example.com:8080"  
        assert parts.path == "/path"
        assert parts.query == "query=1"
        assert parts.fragment == "frag"

class TestClient:
    @patch('httpx.Client')
    @patch('httpx.AsyncClient') 
    @patch('httpx.HTTPTransport')
    @patch('httpx.AsyncHTTPTransport')
    def test_client_init_basic(self, mock_async_transport, mock_transport, 
                              mock_async_client, mock_sync_client):
        client = Client("https://api.example.com")
        
        mock_sync_client.assert_called_once()
        mock_async_client.assert_called_once()
        
        assert isinstance(client.base_url, WebPath)
        assert str(client.base_url) == "https://api.example.com"

    @patch('httpx.Client')
    @patch('httpx.AsyncClient')
    @patch('httpx.HTTPTransport')
    @patch('httpx.AsyncHTTPTransport')
    def test_client_init_with_options(self, mock_async_transport, mock_transport,
                                     mock_async_client, mock_sync_client):
        client = Client(
            "https://api.example.com",
            headers={"Authorization": "Bearer token"},
            retries=3,
            timeout=30
        )
        
        mock_transport.assert_called_once_with(retries=3)
        mock_async_transport.assert_called_once_with(retries=3)
        
        assert client._config["headers"] == {"Authorization": "Bearer token"}
        assert client._config["retries"] == 3
        assert client._config["timeout"] == 30

    @patch('httpx.Client')
    @patch('httpx.AsyncClient')
    @patch('httpx.HTTPTransport')
    @patch('httpx.AsyncHTTPTransport')
    def test_client_context_manager_sync(self, *mocks):
        client = Client("https://api.example.com")
        
        assert client.__enter__() == client
        
        with patch.object(client, 'close'):
            client.__exit__(None, None, None)

    @pytest.mark.asyncio 
    @patch('httpx.Client')
    @patch('httpx.AsyncClient')
    @patch('httpx.HTTPTransport')
    @patch('httpx.AsyncHTTPTransport')
    async def test_client_context_manager_async(self, *mocks):
        client = Client("https://api.example.com")
        
        assert await client.__aenter__() == client
        
        with patch.object(client, 'aclose'):
            await client.__aexit__(None, None, None)


class TestBasicWebPathFunctionality:
    def test_webpath_can_be_created(self):
        path = WebPath("https://api.example.com")
        assert path is not None
        assert str(path) == "https://api.example.com"

    def test_webpath_url_properties_work(self):
        path = WebPath("https://api.example.com/users")
        assert path.scheme == "https"
        assert path.netloc == "api.example.com"
        assert path.path == "/users"

    def test_webpath_name_property(self):
        path = WebPath("https://api.example.com/users/123")
        assert path.name == "123"
        
        path2 = WebPath("https://api.example.com/file.txt")
        assert path2.name == "file.txt"

    def test_http_method_creation(self):
        path = WebPath("https://api.example.com")
        
        get_method = path.get
        post_method = path.post
        
        assert callable(get_method)
        assert callable(post_method)


if __name__ == "__main__":
    pytest.main([__file__])