"""The tests the for Meraki device tracker"""
import asyncio
import json
from unittest.mock import patch
import pytest
from homeassistant.components.device_tracker.meraki import (
    CONF_VALIDATOR, CONF_SECRET)
from homeassistant.setup import async_setup_component
import homeassistant.components.device_tracker as device_tracker
from homeassistant.const import CONF_PLATFORM
from homeassistant.components.device_tracker.meraki import URL


@pytest.fixture
def meraki_client(loop, hass, test_client):
    """Meraki mock client."""
    assert loop.run_until_complete(async_setup_component(
        hass, device_tracker.DOMAIN, {
            device_tracker.DOMAIN: {
                CONF_PLATFORM: 'meraki',
                CONF_VALIDATOR: 'validator',
                CONF_SECRET: 'secret'

            }
        }))

    with patch('homeassistant.components.device_tracker.update_config'):
        yield loop.run_until_complete(test_client(hass.http.app))


@asyncio.coroutine
def test_invalid_or_missing_data(meraki_client):
    """Test validator with invalid or missing data."""

    req = yield from meraki_client.get(URL)
    text = yield from req.text()
    assert req.status == 200
    assert text == 'validator'

    req = yield from meraki_client.post(URL, data=b"invalid")
    text = yield from req.json()
    assert req.status == 400
    assert text['message'] == 'Invalid JSON'

    req = yield from meraki_client.post(URL, data=b"{}")
    text = yield from req.json()
    assert req.status == 422
    assert text['message'] == 'No secret'

    data = {
        "version": "1.0",
        "secret": "secret"
    }
    req = yield from meraki_client.post(URL, data=json.dumps(data))
    text = yield from req.json()
    assert req.status == 422
    assert text['message'] == 'Invalid version'

    data = {
        "version": "2.0",
        "secret": "invalid"
    }
    req = yield from meraki_client.post(URL, data=json.dumps(data))
    text = yield from req.json()
    assert req.status == 422
    assert text['message'] == 'Invalid secret'


@asyncio.coroutine
def test_data_will_be_saved(hass, meraki_client):
    """Test with valid data"""
    data = {
        "version": "2.0",
        "secret": "secret",
        "type": "DevicesSeen",
        "data": {
            "observations": [
                {
                    "location": {
                        "lat": "51.5355157",
                        "lng": "21.0699035",
                        "unc": "46.3610585",
                    },
                    "seenTime": "2016-09-12T16:23:13Z",
                    "ssid": 'ssid',
                    "os": 'HA',
                    "clientMac": "00:26:ab:b8:a9:a4",
                    "seenEpoch": "147369739",
                    "rssi": "20",
                    "manufacturer": "Seiko Epson"
                }
            ]
        }
    }
    req = yield from meraki_client.post(URL, data=json.dumps(data))
    assert req.status == 200
    state_name = hass.states.get('{}.{}'.format('device_tracker',
                                                '0026abb8a9a4')).state
    assert 'home' == state_name
    