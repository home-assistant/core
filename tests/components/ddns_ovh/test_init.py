"""Test the DDNS for OVH component."""
from datetime import timedelta

import pytest

from homeassistant.components import ddns_ovh
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed

DOMAIN = "test.example.com"

PASSWORD = "password"

UPDATE_URL = ddns_ovh.UPDATE_URL

USERNAME = "username"


@pytest.fixture
def setup_ddns_ovh(hass, aioclient_mock):
    """Fixture that sets up DDNS for OVH."""
    aioclient_mock.get(UPDATE_URL, params={"hostname": DOMAIN}, text="good 0.0.0.0")

    hass.loop.run_until_complete(
        async_setup_component(
            hass,
            ddns_ovh.DOMAIN,
            {
                ddns_ovh.DOMAIN: {
                    "domain": DOMAIN,
                    "username": USERNAME,
                    "password": PASSWORD,
                    "triggered_by_event": False,
                }
            },
        )
    )


async def test_setup(hass, aioclient_mock):
    """Test setup works if update passes."""
    aioclient_mock.get(UPDATE_URL, params={"hostname": DOMAIN}, text="nochg 0.0.0.0")

    result = await async_setup_component(
        hass,
        ddns_ovh.DOMAIN,
        {
            ddns_ovh.DOMAIN: {
                "domain": DOMAIN,
                "username": USERNAME,
                "password": PASSWORD,
            }
        },
    )
    assert result
    assert aioclient_mock.call_count == 1

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2


async def test_setup_fails_if_update_fails(hass, aioclient_mock):
    """Test setup fails if first update fails."""
    aioclient_mock.get(UPDATE_URL, params={"hostname": DOMAIN}, text="nohost")

    result = await async_setup_component(
        hass,
        ddns_ovh.DOMAIN,
        {
            ddns_ovh.DOMAIN: {
                "domain": DOMAIN,
                "username": USERNAME,
                "password": PASSWORD,
            }
        },
    )
    assert not result
    assert aioclient_mock.call_count == 1


async def test_setup_fails_if_wrong_auth(hass, aioclient_mock):
    """Test setup fails if first update fails through wrong authentication."""
    aioclient_mock.get(UPDATE_URL, params={"hostname": DOMAIN}, text="badauth")

    result = await async_setup_component(
        hass,
        ddns_ovh.DOMAIN,
        {
            ddns_ovh.DOMAIN: {
                "domain": DOMAIN,
                "username": USERNAME,
                "password": PASSWORD,
            }
        },
    )
    assert not result
    assert aioclient_mock.call_count == 1
