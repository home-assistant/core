"""Testing the functionality of the SmhiDownloader class."""

import aiohttp
from aioresponses import aioresponses
import pytest

from homeassistant.components.smhi.downloader import SmhiDownloader

# Mock data
mock_data = {"key": "value"}


@pytest.mark.asyncio
async def test_successful_download():
    """Test if SmhiDownloader.fetch successfully downloads data for a valid URL."""
    downloader = SmhiDownloader()
    url = "http://example.com/weatherwarnings.json"

    with aioresponses() as m:
        m.get(url, status=200, payload=mock_data)
        async with aiohttp.ClientSession() as session:
            result = await downloader.fetch(session, url)
            assert result == mock_data


@pytest.mark.asyncio
async def test_non_200_response():
    """Test if SmhiDownloader.fetch correctly handles non-200 HTTP responses."""
    downloader = SmhiDownloader()
    url = "http://example.com/weatherwarnings.json"

    with aioresponses() as m:
        m.get(url, status=404)
        async with aiohttp.ClientSession() as session:
            result = await downloader.fetch(session, url)
            assert result is None


@pytest.mark.asyncio
async def test_download_json():
    """Test if SmhiDownloader.download_json correctly downloads and returns JSON data."""
    downloader = SmhiDownloader()
    url = "http://example.com/weatherwarnings.json"

    with aioresponses() as m:
        m.get(url, status=200, payload=mock_data)
        result = await downloader.download_json(url)
        assert result == mock_data
