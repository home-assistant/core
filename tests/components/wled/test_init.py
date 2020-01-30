"""Tests for the WLED integration."""
import aiohttp
from asynctest import patch

from homeassistant.components.wled.const import DOMAIN
from homeassistant.config_entries import ENTRY_STATE_SETUP_RETRY
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant

from tests.components.wled import init_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_config_entry_not_ready(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the WLED configuration entry not ready."""
    aioclient_mock.get("http://example.local:80/json/", exc=aiohttp.ClientError)

    entry = await init_integration(hass, aioclient_mock)
    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the WLED configuration entry unloading."""
    entry = await init_integration(hass, aioclient_mock)
    assert hass.data[DOMAIN]

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data.get(DOMAIN)


async def test_setting_unique_id(hass, aioclient_mock):
    """Test we set unique ID if not set yet."""
    entry = await init_integration(hass, aioclient_mock)

    assert hass.data[DOMAIN]
    assert entry.unique_id == "aabbccddeeff"


async def test_interval_update(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the WLED configuration entry unloading."""
    entry = await init_integration(hass, aioclient_mock, skip_setup=True)

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

    state = hass.states.get("light.wled_rgb_light")
    assert state.state == STATE_ON
