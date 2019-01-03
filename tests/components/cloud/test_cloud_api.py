"""Test cloud API."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.cloud import cloud_api


@pytest.fixture(autouse=True)
def mock_check_token():
    """Mock check token."""
    with patch('homeassistant.components.cloud.auth_api.'
               'check_token') as mock_check_token:
        yield mock_check_token


async def test_create_cloudhook(hass, aioclient_mock):
    """Test creating a cloudhook."""
    aioclient_mock.post('https://example.com/bla', json={
        'cloudhook_id': 'mock-webhook',
        'url': 'https://blabla'
    })
    cloud = Mock(
        hass=hass,
        id_token='mock-id-token',
        cloudhook_create_url='https://example.com/bla',
    )
    resp = await cloud_api.async_create_cloudhook(cloud)
    assert len(aioclient_mock.mock_calls) == 1
    assert await resp.json() == {
        'cloudhook_id': 'mock-webhook',
        'url': 'https://blabla'
    }
