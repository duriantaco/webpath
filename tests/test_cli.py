import pytest
import json
from unittest.mock import Mock, patch
from webpath.cli import get, download

@patch('webpath.cli.WebPath')
def test_get_basic(mock_webpath):
    mock_response = Mock()
    mock_response.headers = {"content-type": "text/plain"}
    mock_response.content = b"hello world"
    
    mock_path = Mock()
    mock_path.get.return_value = mock_response
    mock_webpath.return_value = mock_path
    
    with patch('webpath.cli.sys.stdout.buffer.write') as mock_write:
        get("https://example.com", pretty=False, retries=0, backoff=0.3)
        
        mock_webpath.assert_called_once_with("https://example.com")
        mock_path.get.assert_called_once_with(retries=0, backoff=0.3)
        mock_write.assert_called_once_with(b"hello world")


@patch('webpath.cli.WebPath')
def test_get_with_pretty_json(mock_webpath):
    mock_response = Mock()
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"name": "test", "value": 123}
    
    mock_path = Mock()
    mock_path.get.return_value = mock_response
    mock_webpath.return_value = mock_path
    
    with patch('webpath.cli.rprint') as mock_print:
        get("https://api.example.com", pretty=True, retries=0, backoff=0.3)
        
        expected_json = json.dumps({"name": "test", "value": 123}, indent=2)
        mock_print.assert_called_once_with(expected_json)


@patch('webpath.cli.WebPath')
def test_get_with_retries(mock_webpath):
    mock_response = Mock()
    mock_response.headers = {}
    mock_response.content = b"test"
    
    mock_path = Mock()
    mock_path.get.return_value = mock_response
    mock_webpath.return_value = mock_path
    
    with patch('webpath.cli.sys.stdout.buffer.write'):
        get("https://example.com", pretty=False, retries=5, backoff=1.0)
        
        mock_path.get.assert_called_once_with(retries=5, backoff=1.0)


@patch('webpath.cli.WebPath')
def test_download_basic(mock_webpath):
    mock_path = Mock()
    mock_webpath.return_value = mock_path
    
    with patch('webpath.cli.rprint') as mock_print:
        download("https://example.com/file.zip", "file.zip", retries=3, backoff=0.3, checksum=None)
        
        mock_webpath.assert_called_once_with("https://example.com/file.zip")
        mock_path.download.assert_called_once_with(
            "file.zip", 
            retries=3, 
            backoff=0.3, 
            checksum=None
        )
        mock_print.assert_called_once_with("[green] * [/green] Saved to file.zip")


@patch('webpath.cli.WebPath')
def test_download_with_checksum(mock_webpath):
    mock_path = Mock()
    mock_webpath.return_value = mock_path
    
    with patch('webpath.cli.rprint'):
        download("https://example.com/file.zip", "file.zip", retries=10, backoff=1.5, checksum="abc123")
        
        mock_path.download.assert_called_once_with(
            "file.zip",
            retries=10,
            backoff=1.5,
            checksum="abc123"
        )

if __name__ == "__main__":
    pytest.main([__file__])