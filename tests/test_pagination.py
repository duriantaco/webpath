
import requests_mock
from webpath import WebPath

def test_pagination_cycle_detection():
    """should detect and break pagination cycles"""
    with requests_mock.Mocker() as m:
        m.get("https://api.com/page1", json={
            "data": ["item1", "item2"],
            "next": "https://api.com/page2"
        })
        m.get("https://api.com/page2", json={
            "data": ["item3", "item4"], 
            "next": "https://api.com/page1"
        })
        
        resp = WebPath("https://api.com/page1").get()
        pages = list(resp.paginate(max_pages=10))
        
        assert len(pages) == 2
        assert m.call_count >= 2

def test_pagination_max_pages_limit():
    with requests_mock.Mocker() as m:
        for i in range(5):
            m.get(f"https://api.com/page{i}", json={
                "data": [f"item{i}"],
                "next": f"https://api.com/page{i+1}"
            })
        
        resp = WebPath("https://api.com/page0").get()
        pages = list(resp.paginate(max_pages=3))
        
        assert len(pages) == 3
        assert m.call_count >= 3
