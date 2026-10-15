"""Test the SFR Box setup process."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from sfrbox_api.exceptions import SFRBoxAuthenticationError, SFRBoxError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sfr_box.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


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


@pytest.mark.parametrize(
    ("host", "configuration_url"),
    [
        pytest.param("192.168.0.1", "http://192.168.0.1", id="ip"),
        pytest.param(
            "http://sfrbox.example.com", "http://sfrbox.example.com", id="http_url"
        ),
        pytest.param(
            "https://sfrbox.example.com", "https://sfrbox.example.com", id="https_url"
        ),
    ],
)
@pytest.mark.usefixtures("system_get_info", "dsl_get_info", "wan_get_info")
async def test_device_configuration_url(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    host: str,
    configuration_url: str,
) -> None:
    """Ensure the configuration URL handles a host entered as a URL."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: host}, unique_id="e4:5d:51:00:11:22"
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    assert len(device_entries) == 1
    assert device_entries[0].configuration_url == configuration_url
