"""Tests for Deutscher Wetterdienst (DWD) Weather Warnings integration."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from homeassistant.components.dwd_weather_warnings.const import (
    API_ATTR_WARNING_COLOR,
    API_ATTR_WARNING_DESCRIPTION,
    API_ATTR_WARNING_END,
    API_ATTR_WARNING_HEADLINE,
    API_ATTR_WARNING_INSTRUCTION,
    API_ATTR_WARNING_LEVEL,
    API_ATTR_WARNING_NAME,
    API_ATTR_WARNING_PARAMETERS,
    API_ATTR_WARNING_START,
    API_ATTR_WARNING_TYPE,
    ATTR_WARNING_COUNT,
    CONF_REGION_DEVICE_TRACKER,
    CONF_REGION_IDENTIFIER,
    CURRENT_WARNING_SENSOR,
    DOMAIN,
)
from homeassistant.components.dwd_weather_warnings.coordinator import (
    DwdWeatherWarningsCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType

from . import init_integration

from tests.common import MockConfigEntry


def _warning(level: int, end_time: datetime) -> dict[str, object]:
    """Return a warning payload for tests."""
    return {
        API_ATTR_WARNING_NAME: f"Warning {level}",
        API_ATTR_WARNING_TYPE: level,
        API_ATTR_WARNING_LEVEL: level,
        API_ATTR_WARNING_HEADLINE: f"Headline {level}",
        API_ATTR_WARNING_DESCRIPTION: "Description",
        API_ATTR_WARNING_INSTRUCTION: "Instruction",
        API_ATTR_WARNING_START: end_time - timedelta(hours=1),
        API_ATTR_WARNING_END: end_time,
        API_ATTR_WARNING_PARAMETERS: {},
        API_ATTR_WARNING_COLOR: "#ffffff",
    }


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


async def test_removing_old_device(
    hass: HomeAssistant,
    mock_identifier_entry: MockConfigEntry,
    mock_dwdwfsapi: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing old device when reloading the integration."""

    mock_identifier_entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        identifiers={(DOMAIN, mock_identifier_entry.entry_id)},
        config_entry_id=mock_identifier_entry.entry_id,
        entry_type=DeviceEntryType.SERVICE,
        name="test",
    )

    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, mock_identifier_entry.entry_id)}
        )
        is not None
    )

    await hass.config_entries.async_setup(mock_identifier_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, mock_identifier_entry.entry_id)}
        )
        is None
    )


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


async def test_filter_expired_warnings(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_dwdwfsapi: MagicMock
) -> None:
    """Test expired-warning filtering."""
    now = datetime.now(UTC)
    mock_dwdwfsapi.data_valid = True
    mock_dwdwfsapi.warncell_id = "803000000"
    mock_dwdwfsapi.warncell_name = "Test region"
    mock_dwdwfsapi.current_warnings = [
        _warning(4, now - timedelta(minutes=30)),
        _warning(2, now + timedelta(minutes=30)),
    ]
    mock_dwdwfsapi.expected_warnings = []

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_REGION_IDENTIFIER: "803000000"},
        unique_id="803000000",
    )
    await init_integration(hass, entry)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}-{CURRENT_WARNING_SENSOR}"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "2"
    assert state.attributes[ATTR_WARNING_COUNT] == 1
    assert "warning_2" not in state.attributes
