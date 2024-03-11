"""Test init for Anova."""

from unittest.mock import patch

from anova_wifi import AnovaApi

from homeassistant.components.anova import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import ONLINE_UPDATE, async_init_integration, create_entry


async def test_async_setup_entry(hass: HomeAssistant, anova_api: AnovaApi) -> None:
    """Test a successful setup entry."""
    await async_init_integration(hass)
    state = hass.states.get("sensor.anova_precision_cooker_mode")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "Low water"


async def test_wrong_login(
    hass: HomeAssistant, anova_api_wrong_login: AnovaApi
) -> None:
    """Test for setup failure if connection to Anova is missing."""
    entry = create_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_new_devices(hass: HomeAssistant, anova_api: AnovaApi) -> None:
    """Test for if we find a new device on init."""
    entry = create_entry(hass, "test_device_2")
    with patch(
        "homeassistant.components.anova.coordinator.AnovaPrecisionCooker.update"
    ) as update_patch:
        update_patch.return_value = ONLINE_UPDATE
        assert len(entry.data["devices"]) == 1
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(entry.data["devices"]) == 2


async def test_device_cached_but_offline(
    hass: HomeAssistant, anova_api_no_devices: AnovaApi
) -> None:
    """Test if we have previously seen a device, but it was offline on startup."""
    entry = create_entry(hass)

    with patch(
        "homeassistant.components.anova.coordinator.AnovaPrecisionCooker.update"
    ) as update_patch:
        update_patch.return_value = ONLINE_UPDATE
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(entry.data["devices"]) == 1
    state = hass.states.get("sensor.anova_precision_cooker_mode")
    assert state is not None
    assert state.state == "Low water"


async def test_unload_entry(hass: HomeAssistant, anova_api: AnovaApi) -> None:
    """Test successful unload of entry."""
    entry = await async_init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
