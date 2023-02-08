"""Test the Google Domains component."""
from datetime import timedelta

import pytest

from homeassistant.components import google_domains
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

DOMAIN = "test.example.com"
USERNAME = "abc123"
PASSWORD = "xyz789"

UPDATE_URL = f"https://{USERNAME}:{PASSWORD}@domains.google.com/nic/update"


@pytest.fixture
def setup_google_domains(hass, aioclient_mock):
    """Fixture that sets up NamecheapDNS."""
    aioclient_mock.get(UPDATE_URL, params={"hostname": DOMAIN}, text="ok 0.0.0.0")

    hass.loop.run_until_complete(
        async_setup_component(
            hass,
            google_domains.DOMAIN,
            {
                "google_domains": {
                    "domain": DOMAIN,
                    "username": USERNAME,
                    "password": PASSWORD,
                }
            },
        )
    )


async def test_setup(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test setup works if update passes."""
    aioclient_mock.get(UPDATE_URL, params={"hostname": DOMAIN}, text="nochg 0.0.0.0")

    result = await async_setup_component(
        hass,
        google_domains.DOMAIN,
        {
            "google_domains": {
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


async def test_setup_fails_if_update_fails(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup fails if first update fails."""
    aioclient_mock.get(UPDATE_URL, params={"hostname": DOMAIN}, text="nohost")

    result = await async_setup_component(
        hass,
        google_domains.DOMAIN,
        {
            "google_domains": {
                "domain": DOMAIN,
                "username": USERNAME,
                "password": PASSWORD,
            }
        },
    )
    assert not result
    assert aioclient_mock.call_count == 1
