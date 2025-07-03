from webpath import WebPath

def test_query_with_lists():
    url = WebPath("https://api.com").with_query(tags=["python", "web"], limit=10)
    assert "tags=python" in str(url)
    assert "tags=web" in str(url)
    assert "limit=10" in str(url)

def test_query_with_none_removes_param():
    url = WebPath("https://api.com?existing=value&remove=old")
    updated = url.with_query(remove=None, new="added")
    
    assert "remove=" not in str(updated)
    assert "existing=value" in str(updated)
    assert "new=added" in str(updated)

def test_query_preserves_existing():
    """with_query should preserve existing parameters"""
    url = WebPath("https://api.com?keep=this&modify=old")
    updated = url.with_query(modify="new", add="more")
    
    assert "keep=this" in str(updated)
    assert "modify=new" in str(updated)
    assert "add=more" in str(updated)
    assert "modify=old" not in str(updated)

def test_query_with_tuples():
    url = WebPath("https://api.com").with_query(coords=(1.23, 4.56))
    assert "coords=1.23" in str(url)
    assert "coords=4.56" in str(url)
