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


async def test_create_webhook(hass, aioclient_mock):
    """Test creating a webhook."""
    aioclient_mock.post('https://example.com/bla', json={
        'webhook_id': 'mock-webhook'
    })
    cloud = Mock(
        hass=hass,
        id_token='mock-id-token',
        cloudhook_create_url='https://example.com/bla',
    )
    await cloud_api.async_create_cloudhook(cloud, 'mock-webhook')
    assert len(aioclient_mock.mock_calls) == 1
