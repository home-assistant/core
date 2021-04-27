"""Test init of Nettigo Air Monitor integration."""
from unittest.mock import patch

from nettigo_air_monitor import ApiError

from homeassistant.components.nam.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import STATE_UNAVAILABLE

from tests.common import MockConfigEntry
from tests.components.nam import init_integration


async def test_async_setup_entry(hass):
    """Test a successful setup entry."""
    await init_integration(hass)

    state = hass.states.get("air_quality.nettigo_air_monitor_sds011")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "11"


async def test_config_not_ready(hass):
    """Test for setup failure if the connection to the device fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="10.10.2.3",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"host": "10.10.2.3"},
    )

    with patch(
        "homeassistant.components.nam.NettigoAirMonitor._async_get_data",
        side_effect=ApiError("API Error"),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)
