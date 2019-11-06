"""Tests for the WLED integration."""
import aiohttp
from asynctest import patch
import pytest

from homeassistant.components.wled import async_setup_entry
from homeassistant.components.wled.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry, load_fixture
from tests.components.wled import init_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_config_entry_not_ready(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the WLED configuration entry not ready."""
    aioclient_mock.get("http://example.local:80/json/", exc=aiohttp.ClientError)

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "example.local", CONF_MAC: "aabbccddeeff"}
    )

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, entry)
        await hass.async_block_till_done()


async def test_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the WLED configuration entry unloading."""
    entry = await init_integration(hass, aioclient_mock)
    assert hass.data[DOMAIN]

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data.get(DOMAIN)


async def test_interval_update(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the WLED configuration entry unloading."""
    aioclient_mock.get(
        "http://example.local:80/json/",
        text=load_fixture("wled.json"),
        headers={"Content-Type": "application/json"},
    )

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "example.local", CONF_MAC: "aabbccddeeff"}
    )
    entry.add_to_hass(hass)

    interval_action = False

    def async_track_time_interval(hass, action, interval):
        nonlocal interval_action
        interval_action = action

    with patch(
        "homeassistant.components.wled.async_track_time_interval",
        new=async_track_time_interval,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert interval_action
    await interval_action()  # pylint: disable=not-callable
    await hass.async_block_till_done()

    state = hass.states.get("light.wled_light")
    assert state.state == STATE_ON
