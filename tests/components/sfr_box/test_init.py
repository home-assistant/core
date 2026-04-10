"""Test the SFR Box setup process."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from sfrbox_api.exceptions import SFRBoxAuthenticationError, SFRBoxError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sfr_box.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.sfr_box.PLATFORMS", []):
        yield


@pytest.mark.usefixtures("system_get_info", "dsl_get_info", "wan_get_info")
async def test_setup_unload_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test entry setup and unload."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    # Unload the entry and verify that the data has been removed
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_exception(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test ConfigEntryNotReady when API raises an exception during entry setup."""
    with patch(
        "homeassistant.components.sfr_box.coordinator.SFRBox.system_get_info",
        side_effect=SFRBoxError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_exception(
    hass: HomeAssistant, config_entry_with_auth: ConfigEntry
) -> None:
    """Test ConfigEntryNotReady when API raises an exception during authentication."""
    with patch(
        "homeassistant.components.sfr_box.coordinator.SFRBox.authenticate",
        side_effect=SFRBoxError,
    ):
        await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry_with_auth.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_invalid_auth(
    hass: HomeAssistant, config_entry_with_auth: ConfigEntry
) -> None:
    """Test ConfigEntryAuthFailed when API raises an exception during authentication."""
    with patch(
        "homeassistant.components.sfr_box.coordinator.SFRBox.authenticate",
        side_effect=SFRBoxAuthenticationError,
    ):
        await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry_with_auth.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.usefixtures("system_get_info", "dsl_get_info", "wan_get_info")
async def test_device_registry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Ensure devices are correctly registered."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure devices are correctly registered
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    assert device_entries == snapshot
