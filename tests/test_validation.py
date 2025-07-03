
from webpath import WebPath
import pytest

def test_webpath_requires_scheme():
    with pytest.raises(ValueError, match="must include scheme"):
        WebPath("example.com/path")

def test_webpath_rejects_non_http_schemes():
    with pytest.raises(ValueError, match="Only http/https schemes supported"):
        WebPath("ftp://example.com/file")
    
    with pytest.raises(ValueError, match="Only http/https schemes supported"):
        WebPath("file:///etc/passwd")

def test_webpath_requires_hostname():
    with pytest.raises(ValueError, match="must include hostname"):
        WebPath("https:///path/only")

def test_webpath_empty_url():
    with pytest.raises(ValueError, match="cannot be empty"):
        WebPath("")
    
    with pytest.raises(ValueError, match="cannot be empty"):
        WebPath("   ")