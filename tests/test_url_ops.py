from webpath import WebPath
import pytest

def test_join_and_query():
    api = WebPath("https://a.com/v1")
    url = (api / "users" / 5).with_query(foo=["x", "y"])
    assert str(url) == "https://a.com/v1/users/5?foo=x&foo=y"
    assert url.parent.name == "users"
    assert url.suffix == ""

def test_trailing_slash_preserved():
    a = WebPath("https://x.org/folder/")
    b = a / "file"
    assert str(b) == "https://x.org/folder/file"
    assert str(a.ensure_trailing_slash()) == "https://x.org/folder/"

def test_fragment_and_trailing_slash():
    u = WebPath("https://x.org/y/").with_fragment("sec-2")
    assert str(u) == "https://x.org/y/#sec-2"
    assert u.ensure_trailing_slash().path.endswith("/")

def test_suffix_logic():
    png = WebPath("https://x.org/logo.png")
    assert png.suffix == ".png"
    assert png.name == "logo.png"

def test_idna_conversion():
    url = WebPath("https://bücher.de/") / "seite"
    assert url.host == "xn--bcher-kva.de"
    assert str(url) == "https://bücher.de/seite"

def test_percent_encoding():
    u = WebPath("https://x.org") / "white space" / "✓"
    assert str(u) == "https://x.org/white%20space/%E2%9C%93"

def test_non_http_scheme_get():
    with pytest.raises(ValueError, match="Only http/https schemes supported"):
        url = WebPath("ftp://example.com/file")
