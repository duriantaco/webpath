import requests_mock
from webpath import WebPath
from urllib.parse import urlparse
import sys
import types

def test_retries():
    target = WebPath("https://example.org/res")

    with requests_mock.Mocker() as m:
        # first two calls fail, third returns 200
        m.get("https://example.org/res", [
            {'status_code': 503},
            {'status_code': 503},
            {'status_code': 200, 'text': 'ok'},
        ])
        r = target.get(retries=3, backoff=0)   # no sleep in tests
        assert r.status_code == 200
        assert r.text == "ok"
        assert m.call_count == 3

def test_download_without_tqdm(tmp_path, monkeypatch):
    # pretend tqdm is missing
    monkeypatch.setitem(sys.modules, "tqdm", types.ModuleType("tqdm_missing"))
    data = b"x"*100
    target = tmp_path / "x.bin"
    with requests_mock.Mocker() as m:
        m.get("https://y/z", content=data, headers={"content-length": "100"})
        WebPath("https://y/z").download(target, progress=True)
    assert target.stat().st_size == 100


def test_session_reuse():
    url = WebPath("https://api.ex/x")
    with requests_mock.Mocker() as m:
        m.get("https://api.ex/x", text="foo")
        m.post("https://api.ex/x", text="bar")
        with url.session() as call:
            r1 = call("get")
            r2 = call("post")
    assert r1.text == "foo" and r2.text == "bar"

