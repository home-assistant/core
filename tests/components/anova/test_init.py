"""Test init for Anova."""

from anova_wifi import AnovaApi

from homeassistant.components.anova.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import async_init_integration, create_entry


async def test_async_setup_entry(hass: HomeAssistant, anova_api: AnovaApi) -> None:
    """Test a successful setup entry."""
    await async_init_integration(hass)
    state = hass.states.get("sensor.anova_precision_cooker_mode")
    assert state is not None
    assert state.state == "idle"


async def test_wrong_login(
    hass: HomeAssistant, anova_api_wrong_login: AnovaApi
) -> None:
    """Test for setup failure if connection to Anova is missing."""
    entry = create_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant, anova_api: AnovaApi) -> None:
    """Test successful unload of entry."""
    entry = await async_init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_no_devices_found(
    hass: HomeAssistant,
    anova_api_no_devices: AnovaApi,
) -> None:
    """Test when there don't seem to be any devices on the account."""
    entry = await async_init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_websocket_failure(
    hass: HomeAssistant,
    anova_api_websocket_failure: AnovaApi,
) -> None:
    """Test that we successfully handle a websocket failure on setup."""
    entry = await async_init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
