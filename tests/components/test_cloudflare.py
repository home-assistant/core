"""Test the Cloudflare component."""
import asyncio
from datetime import timedelta
import json
from unittest.mock import patch
import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components import cloudflare
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed

API_KEY = 'abc123'
CONTENT = '1.2.3.4'
DOMAIN = 'https://test.example.com'
EMAIL = 'test@example.com'
PROXIED = False
RECORD_IDENTIFIER = '4456789012'
RECORD_TYPE = 'A'
TIMEOUT = 300
TTL = 1
ZONE = 'asdf123jkl'

BASE_URL = cloudflare.API_BASE_URL.format(ZONE)
UPDATE_URL = cloudflare.UPDATE_URL.format(ZONE, RECORD_IDENTIFIER)

SUCCESS_JSON_RESPONSE = {
    "success": True,
    "errors": [{}],
    "messages": [{}],
    "result": {
        "id": "372e67954025e0ba6aaa6d586b9e0b59",
        "type": "A",
        "name": "test.example.com",
        "content": "1.2.3.4",
        "proxiable": True,
        "proxied": False,
        "ttl": 1,
        "locked": False,
        "zone_id": "asdf123jkl",
        "data": {}
    }
}

GET_DNS_RECORD_RESPONSE = {
    "success": True,
    "errors": [{}],
    "messages": [{}],
    "result": [{
        "id": "372e67954025e0ba6aaa6d586b9e0b59",
        "type": "A",
        "name": "test.example.com",
        "content": "1.2.3.4",
        "proxiable": True,
        "proxied": False,
        "ttl": 1,
        "locked": False,
        "zone_id": "asdf123jkl",
        "data": {}
    }],
    "result_info": {
        "page": 1,
        "per_page": 20,
        "count": 1,
        "total_count": 2000
    }
}

FAIL_JSON_RESPONSE = {
    "success": False,
    "errors": [{
        'code': 6003,
        'error_chain': [{
            'code': 6105,
            'message': 'Invalid Content-Type header'}],
        'message': 'Invalid request headers'}],
    "messages": [],
    "result": None
}

DATA = json.dumps({
    'type': RECORD_TYPE,
    'name': DOMAIN,
    'content': CONTENT,
    'ttl': TTL,
    'proxied': PROXIED,
})

HEADERS = {
    "X-Auth-Email": EMAIL,
    "X-Auth-Key": API_KEY,
    "Content-Type": "application/json",
}

PARAMS = {
    'name': DOMAIN,
}


@pytest.fixture
@asyncio.coroutine
def _mock_get_record_identifier():
    with patch(('homeassistant.components.cloudflare.'
                '_get_record_identifier')) as mock:
        mock.iter.return_value = iter([RECORD_IDENTIFIER])
        yield mock


@pytest.fixture
@asyncio.coroutine
def _mock_get_ip():
    with patch('homeassistant.components.cloudflare._get_ip') as mock:
        mock.iter.return_value = iter([CONTENT])
        yield mock


@pytest.fixture
def setup_cloudflare(hass, aioclient_mock):
    """Fixture that sets up Cloudflare."""
    aioclient_mock.put(UPDATE_URL, data=DATA, headers=HEADERS,
                       json=SUCCESS_JSON_RESPONSE)
    hass.loop.run_until_complete(async_setup_component(
        hass, cloudflare.DOMAIN, {
            'cloudflare': {
                'api_key': API_KEY,
                'domain': DOMAIN,
                'email': EMAIL,
                'record_type': RECORD_TYPE,
                'zone': ZONE,
            }
        }))


# @asyncio.coroutine
# def test_setup(hass, aioclient_mock):
#     """Test setup works if update passes."""
    # aioclient_mock.put(UPDATE_URL, data=DATA, headers=HEADERS,
    #     json=SUCCESS_JSON_RESPONSE)

#     result = yield from async_setup_component(hass, cloudflare.DOMAIN, {
#         'cloudflare': {
#             'api_key': API_KEY,
#             'domain': DOMAIN,
#             'email': EMAIL,
#             'record_type': RECORD_TYPE,
#             'zone': ZONE,
#             'proxied': PROXIED,
#             'timeout': TIMEOUT,
#             'ttl': TTL
#         }
#     })
#     assert result
#     assert aioclient_mock.call_count == 1

#     async_fire_time_changed(hass, utcnow() + timedelta(seconds=TIMEOUT))
#     yield from hass.async_block_till_done()
#     assert aioclient_mock.call_count == 2


# @asyncio.coroutine
# def test_setup_fails_if_update_fails(hass, aioclient_mock,
#     _mock_get_record_identifier, _mock_get_ip):
#     """Test setup fails if first update fails."""
#     aioclient_mock.put(UPDATE_URL, data=DATA, headers=HEADERS,
#         json=SUCCESS_JSON_RESPONSE)

#     result = yield from async_setup_component(hass, cloudflare.DOMAIN, {
#         'cloudflare': {
#             'api_key': API_KEY,
#             'domain': DOMAIN,
#             'email': EMAIL,
#             'record_type': RECORD_TYPE,
#             'zone': ZONE,
#             'proxied': PROXIED,
#             'timeout': TIMEOUT,
#             'ttl': TTL
#         }
#     })
#     assert not result
#     assert aioclient_mock.call_count == 1


@asyncio.coroutine
def test_setup_fails_if_no_ip(
        hass, aioclient_mock, _mock_get_record_identifier, _mock_get_ip):
    """Test setup fails if first update fails."""
    aioclient_mock.put(UPDATE_URL, data=DATA, headers=HEADERS,
                       json=SUCCESS_JSON_RESPONSE)

    result = yield from async_setup_component(hass, cloudflare.DOMAIN, {
        'cloudflare': {
            'api_key': API_KEY,
            'domain': DOMAIN,
            'email': EMAIL,
            'record_type': RECORD_TYPE,
            'zone': ZONE,
            'proxied': PROXIED,
            'timeout': TIMEOUT,
            'ttl': TTL
        }
    })
    assert not result
    assert aioclient_mock.call_count == 0


@asyncio.coroutine
def test_setup_fails_if_no_record_identifier(
        hass, aioclient_mock, _mock_get_record_identifier, _mock_get_ip):
    """Test setup fails if first update fails."""
    aioclient_mock.put(UPDATE_URL, data=DATA, headers=HEADERS,
                       json=SUCCESS_JSON_RESPONSE)

    result = yield from async_setup_component(hass, cloudflare.DOMAIN, {
        'cloudflare': {
            'api_key': API_KEY,
            'domain': DOMAIN,
            'email': EMAIL,
            'record_type': RECORD_TYPE,
            'zone': ZONE,
            'proxied': PROXIED,
            'timeout': TIMEOUT,
            'ttl': TTL
        }
    })
    assert not result
    assert aioclient_mock.call_count == 0
