"""Tests for the Gatus integration setup and unload lifecycle."""

from unittest.mock import patch

from homeassistant.components.gatus.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(hass: HomeAssistant) -> None:
    """Test standard successful setup and unload cycle of the integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://gatus.local"},
        entry_id="gatus_init_test_entry",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gatus.coordinator.GatusDataUpdateCoordinator._async_update_data",
        return_value=[{"key": "endpoint_1", "is_up": True}],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_failing_first_refresh(hass: HomeAssistant) -> None:
    """Test setup failure when the initial coordinator data fetch fails."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://gatus.local"},
        entry_id="gatus_init_fail_entry",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gatus.coordinator.GatusDataUpdateCoordinator._async_update_data",
        side_effect=UpdateFailed("Cannot connect to remote Gatus server instance"),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
