"""The tests the for Meraki device tracker."""

from asyncio import AbstractEventLoop
from http import HTTPStatus
import json

from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components import device_tracker
from homeassistant.components.device_tracker import legacy
from homeassistant.components.meraki.device_tracker import (
    CONF_SECRET,
    CONF_VALIDATOR,
    URL,
)
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


@pytest.fixture
def meraki_client(
    event_loop: AbstractEventLoop,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> TestClient:
    """Meraki mock client."""
    loop = event_loop

    async def setup_and_wait():
        result = await async_setup_component(
            hass,
            device_tracker.DOMAIN,
            {
                device_tracker.DOMAIN: {
                    CONF_PLATFORM: "meraki",
                    CONF_VALIDATOR: "validator",
                    CONF_SECRET: "secret",
                }
            },
        )
        await hass.async_block_till_done()
        return result

    assert loop.run_until_complete(setup_and_wait())
    return loop.run_until_complete(hass_client())


async def test_invalid_or_missing_data(
    mock_device_tracker_conf: list[legacy.Device], meraki_client
) -> None:
    """Test validator with invalid or missing data."""
    req = await meraki_client.get(URL)
    text = await req.text()
    assert req.status == HTTPStatus.OK
    assert text == "validator"

    req = await meraki_client.post(URL, data=b"invalid")
    text = await req.json()
    assert req.status == HTTPStatus.BAD_REQUEST
    assert text["message"] == "Invalid JSON"

    req = await meraki_client.post(URL, data=b"{}")
    text = await req.json()
    assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert text["message"] == "No secret"

    data = {"version": "1.0", "secret": "secret"}
    req = await meraki_client.post(URL, data=json.dumps(data))
    text = await req.json()
    assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert text["message"] == "Invalid version"

    data = {"version": "2.0", "secret": "invalid"}
    req = await meraki_client.post(URL, data=json.dumps(data))
    text = await req.json()
    assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert text["message"] == "Invalid secret"

    data = {"version": "2.0", "secret": "secret", "type": "InvalidType"}
    req = await meraki_client.post(URL, data=json.dumps(data))
    text = await req.json()
    assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert text["message"] == "Invalid device type"

    data = {
        "version": "2.0",
        "secret": "secret",
        "type": "BluetoothDevicesSeen",
        "data": {"observations": []},
    }
    req = await meraki_client.post(URL, data=json.dumps(data))
    assert req.status == HTTPStatus.OK


async def test_data_will_be_saved(
    mock_device_tracker_conf: list[legacy.Device], hass: HomeAssistant, meraki_client
) -> None:
    """Test with valid data."""
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
                    "ssid": "ssid",
                    "os": "HA",
                    "ipv6": "2607:f0d0:1002:51::4/64",
                    "clientMac": "00:26:ab:b8:a9:a4",
                    "seenEpoch": "147369739",
                    "rssi": "20",
                    "manufacturer": "Seiko Epson",
                },
                {
                    "location": {
                        "lat": "51.5355357",
                        "lng": "21.0699635",
                        "unc": "46.3610585",
                    },
                    "seenTime": "2016-09-12T16:21:13Z",
                    "ssid": "ssid",
                    "os": "HA",
                    "ipv4": "192.168.0.1",
                    "clientMac": "00:26:ab:b8:a9:a5",
                    "seenEpoch": "147369750",
                    "rssi": "20",
                    "manufacturer": "Seiko Epson",
                },
            ]
        },
    }
    req = await meraki_client.post(URL, data=json.dumps(data))
    assert req.status == HTTPStatus.OK
    await hass.async_block_till_done()
    state_name = hass.states.get(
        "{}.{}".format("device_tracker", "00_26_ab_b8_a9_a4")
    ).state
    assert state_name == "home"

    state_name = hass.states.get(
        "{}.{}".format("device_tracker", "00_26_ab_b8_a9_a5")
    ).state
    assert state_name == "home"
