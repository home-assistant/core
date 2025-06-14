"""Test the FreeDNS component."""

import pytest

from homeassistant.components import freedns
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

ACCESS_TOKEN = "test_token"
UPDATE_INTERVAL = freedns.DEFAULT_INTERVAL
UPDATE_URL = freedns.UPDATE_URL


@pytest.fixture
async def setup_freedns(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Fixture that sets up FreeDNS."""
    params = {}
    params[ACCESS_TOKEN] = ""
    aioclient_mock.get(
        UPDATE_URL, params=params, text="Successfully updated 1 domains."
    )

    await async_setup_component(
        hass,
        freedns.DOMAIN,
        {
            freedns.DOMAIN: {
                "access_token": ACCESS_TOKEN,
                "scan_interval": UPDATE_INTERVAL,
            }
        },
    )


async def test_setup(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test setup works if update passes."""
    params = {}
    params[ACCESS_TOKEN] = ""
    aioclient_mock.get(
        UPDATE_URL, params=params, text="ERROR: Address has not changed."
    )

    result = await async_setup_component(
        hass,
        freedns.DOMAIN,
        {
            freedns.DOMAIN: {
                "access_token": ACCESS_TOKEN,
                "scan_interval": UPDATE_INTERVAL,
            }
        },
    )
    assert result
    assert aioclient_mock.call_count == 1

    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2


async def test_setup_fails_if_wrong_token(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup fails if first update fails through wrong token."""
    params = {}
    params[ACCESS_TOKEN] = ""
    aioclient_mock.get(UPDATE_URL, params=params, text="ERROR: Invalid update URL (2)")

    result = await async_setup_component(
        hass,
        freedns.DOMAIN,
        {
            freedns.DOMAIN: {
                "access_token": ACCESS_TOKEN,
                "scan_interval": UPDATE_INTERVAL,
            }
        },
    )
    assert not result
    assert aioclient_mock.call_count == 1
