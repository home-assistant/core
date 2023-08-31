"""Test the No-IP.com component."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

import pytest

from homeassistant.components import no_ip
from homeassistant.config_entries import ConfigEntry, UnknownEntry
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

DOMAIN = "test.example.com"

PASSWORD = "xyz789"

UPDATE_URL = no_ip.const.UPDATE_URL

USERNAME = "abc@123.com"


@pytest.fixture
def setup_no_ip(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Fixture that sets up NO-IP."""
    aioclient_mock.get(UPDATE_URL, params={"hostname": DOMAIN}, text="good 0.0.0.0")

    hass.loop.run_until_complete(
        async_setup_component(
            hass,
            no_ip.const.DOMAIN,
            {
                no_ip.const.DOMAIN: {
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
        no_ip.const.DOMAIN,
        {
            no_ip.const.DOMAIN: {
                "domain": DOMAIN,
                "username": USERNAME,
                "password": PASSWORD,
            }
        },
    )
    assert result
    assert aioclient_mock.call_count == 2

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 3


@pytest.mark.parametrize(
    ("result_text", "counter"),
    [
        ("good 192.168.1.1", 2),
        ("nochg 192.168.1.1", 2),
        ("badauth", 1),
        ("badagent", 1),
        ("nohost", 1),
    ],
)
async def test_setup_fails(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    result_text: str,
    counter: int,
) -> None:
    """Test setup fails if first update fails through wrong authentication."""
    aioclient_mock.get(UPDATE_URL, params={"hostname": DOMAIN}, text=result_text)

    result = await async_setup_component(
        hass,
        no_ip.const.DOMAIN,
        {
            no_ip.const.DOMAIN: {
                "domain": DOMAIN,
                "username": USERNAME,
                "password": PASSWORD,
            }
        },
    )
    assert result
    assert aioclient_mock.call_count == counter


async def test_update_listener(hass: HomeAssistant) -> None:
    """Test update_listener."""
    config_entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test",
        source="test",
        data={
            "domain": DOMAIN,
            "username": USERNAME,
            "password": PASSWORD,
        },
    )

    # Assign the separate function update_listener to the ConfigEntry as a method
    config_entry.add_update_listener(no_ip.update_listener)

    # Mock the async_reload method of the config_entries object
    config_entry_mock = Mock()
    config_entry_mock.async_reload = Mock(side_effect=UnknownEntry)

    # Execute the update_listener function and pass the mock instance as an argument
    with pytest.raises(UnknownEntry):
        await no_ip.update_listener(hass, config_entry_mock)
