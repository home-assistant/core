"""Test Axis component setup process."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import axis
from homeassistant.components.axis.const import CONF_COMPANION
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .const import (
    API_DISCOVERY_BASIC_DEVICE_INFO,
    BASIC_DEVICE_INFO_COMPANION_RESPONSE,
    BASIC_DEVICE_INFO_RESPONSE,
    DEFAULT_HOST,
    MODEL,
    NAME,
)


async def test_setup_entry(config_entry_setup: MockConfigEntry) -> None:
    """Test successful setup of entry."""
    assert config_entry_setup.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "config_entry_data",
    [
        {
            CONF_HOST: DEFAULT_HOST,
            CONF_USERNAME: "root",
            CONF_PASSWORD: "pass",
            CONF_PORT: 80,
            CONF_MODEL: MODEL,
            CONF_NAME: NAME,
        }
    ],
)
@pytest.mark.parametrize(
    ("api_discovery_items", "basic_device_info_payload", "companion"),
    [
        ({}, BASIC_DEVICE_INFO_RESPONSE, False),
        (API_DISCOVERY_BASIC_DEVICE_INFO, BASIC_DEVICE_INFO_COMPANION_RESPONSE, True),
    ],
)
async def test_setup_entry_stores_companion(
    config_entry_setup: MockConfigEntry, companion: bool
) -> None:
    """Test setup stores the companion flag for entries created without it."""
    assert config_entry_setup.state is ConfigEntryState.LOADED
    assert config_entry_setup.data[CONF_COMPANION] is companion
    assert config_entry_setup.runtime_data.api.config.is_companion is companion


async def test_setup_entry_fails(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test failed setup of entry."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.axis.get_axis_api",
        side_effect=axis.CannotConnect,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Test successful unload of entry."""
    assert config_entry_setup.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry_setup.entry_id)
    assert config_entry_setup.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("config_entry_version", [1])
async def test_migrate_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test successful migration of entry data."""
    config_entry.add_to_hass(hass)
    assert config_entry.version == 1

    mock_device = Mock()
    mock_device.async_setup = AsyncMock()
    mock_device.async_update_device_registry = AsyncMock()
    mock_device.api.vapix.light_control = None
    mock_device.api.vapix.params.image_format = None

    with patch("homeassistant.components.axis.async_setup_entry", return_value=None):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.version == 3
