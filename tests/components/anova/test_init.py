"""Test init for Anova."""

from unittest.mock import patch

from anova_wifi import AnovaOffline

from homeassistant.components.anova import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import async_init_integration, create_entry


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test a successful setup entry."""
    await async_init_integration(hass)
    state = hass.states.get("sensor.mode")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "Low water"


async def test_config_not_ready(hass: HomeAssistant) -> None:
    """Test for setup failure if connection to Anova is missing."""
    entry = create_entry(hass)
    with patch(
        "anova_wifi.AnovaPrecisionCooker.update",
        side_effect=AnovaOffline(),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    entry = await async_init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
