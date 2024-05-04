"""Tests for Deutscher Wetterdienst (DWD) Weather Warnings integration."""

from unittest.mock import MagicMock

from homeassistant.components.dwd_weather_warnings.const import (
    CONF_REGION_DEVICE_TRACKER,
    DOMAIN,
)
from homeassistant.components.dwd_weather_warnings.coordinator import (
    DwdWeatherWarningsCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_identifier_entry: MockConfigEntry,
    mock_dwdwfsapi: MagicMock,
) -> None:
    """Test loading and unloading the integration with a region identifier based entry."""
    entry = await init_integration(hass, mock_identifier_entry)

    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, DwdWeatherWarningsCoordinator)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_load_invalid_registry_entry(
    hass: HomeAssistant, mock_tracker_entry: MockConfigEntry
) -> None:
    """Test loading the integration with an invalid registry entry ID."""
    INVALID_DATA = mock_tracker_entry.data.copy()
    INVALID_DATA[CONF_REGION_DEVICE_TRACKER] = "invalid_registry_id"

    entry = await init_integration(
        hass, MockConfigEntry(domain=DOMAIN, data=INVALID_DATA)
    )
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_missing_device_tracker(
    hass: HomeAssistant, mock_tracker_entry: MockConfigEntry
) -> None:
    """Test loading the integration with a missing device tracker."""
    entry = await init_integration(hass, mock_tracker_entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_missing_required_attribute(
    hass: HomeAssistant, mock_tracker_entry: MockConfigEntry
) -> None:
    """Test loading the integration with a device tracker missing a required attribute."""
    mock_tracker_entry.add_to_hass(hass)
    hass.states.async_set(
        mock_tracker_entry.data[CONF_REGION_DEVICE_TRACKER],
        STATE_HOME,
        {ATTR_LONGITUDE: "7.610263"},
    )

    await hass.config_entries.async_setup(mock_tracker_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_tracker_entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_valid_device_tracker(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_tracker_entry: MockConfigEntry,
    mock_dwdwfsapi: MagicMock,
) -> None:
    """Test loading the integration with a valid device tracker based entry."""
    mock_tracker_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "device_tracker",
        mock_tracker_entry.domain,
        "uuid",
        suggested_object_id="test_gps",
        config_entry=mock_tracker_entry,
    )

    hass.states.async_set(
        mock_tracker_entry.data[CONF_REGION_DEVICE_TRACKER],
        STATE_HOME,
        {ATTR_LATITUDE: "50.180454", ATTR_LONGITUDE: "7.610263"},
    )

    await hass.config_entries.async_setup(mock_tracker_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_tracker_entry.state is ConfigEntryState.LOADED
    assert isinstance(mock_tracker_entry.runtime_data, DwdWeatherWarningsCoordinator)
