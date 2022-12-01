"""Test the DDNS for OVH component."""

import pytest

from homeassistant.components import ddns_ovh
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

DOMAIN = "test.example.com"

PASSWORD = "password"

UPDATE_URL = ddns_ovh.UPDATE_URL

USERNAME = "username"

EXPECTED_ID = "192.168.0.1"


@pytest.fixture
def setup_ddns_ovh(hass, aioclient_mock):
    """Fixture that sets up DDNS for OVH."""
    aioclient_mock.get(
        UPDATE_URL,
        params={"hostname": DOMAIN, "myip": EXPECTED_ID},
        text="good " + EXPECTED_ID,
    )

    hass.loop.run_until_complete(
        async_setup_component(
            hass,
            ddns_ovh.DOMAIN,
            {
                ddns_ovh.DOMAIN: {
                    "domain": DOMAIN,
                    "username": USERNAME,
                    "password": PASSWORD,
                    "triggered_by_event": True,
                }
            },
        )
    )


async def test_setup(hass: HomeAssistant, aioclient_mock):
    """Test setup works if update passes."""
    aioclient_mock.get(
        UPDATE_URL,
        params={"hostname": DOMAIN, "myip": EXPECTED_ID},
        text="nochg 0.0.0.0",
    )

    result = await async_setup_component(
        hass,
        ddns_ovh.DOMAIN,
        {
            ddns_ovh.DOMAIN: {
                "domain": DOMAIN,
                "username": USERNAME,
                "password": PASSWORD,
                "triggered_by_event": True,
            }
        },
    )
    assert result
    hass.bus.fire("external_ip_provided_event", {"ip": EXPECTED_ID})
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1
