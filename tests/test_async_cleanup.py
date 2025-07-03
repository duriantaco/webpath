import asyncio
import pytest
from webpath import WebPath

@pytest.mark.asyncio
async def test_async_client_cleanup():
    resp = await WebPath("https://httpbin.org/json").aget()
    assert resp.status_code == 200
    
    resp2 = await WebPath("https://httpbin.org/uuid").aget()
    assert resp2.status_code == 200