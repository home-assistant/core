"""Tests for our aiohttp mocker."""
from .aiohttp import AiohttpClientMocker

import pytest


async def test_matching_url():
    """Test we can match urls."""
    mocker = AiohttpClientMocker()
    mocker.get('http://example.com')
    await mocker.match_request('get', 'http://example.com/')

    mocker.clear_requests()

    with pytest.raises(AssertionError):
        await mocker.match_request('get', 'http://example.com/')

    mocker.clear_requests()

    mocker.get('http://example.com?a=1')
    await mocker.match_request('get', 'http://example.com/',
                               params={'a': 1, 'b': 2})
