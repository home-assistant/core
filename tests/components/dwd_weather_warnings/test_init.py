"""Tests for Deutscher Wetterdienst (DWD) Weather Warnings integration."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

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
    DEFAULT_SCAN_INTERVAL,
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
from homeassistant.helpers.update_coordinator import (
    UpdateFailed,
    UpdateFailedUnreachable,
)
from homeassistant.util import dt as dt_util

from . import init_integration


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
    """Test loading and unloading the integration with a region identifier entry."""
    mock_dwdwfsapi.data_valid = True
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
        device_registry.async_get_device_by_identifier(
            (DOMAIN, mock_identifier_entry.entry_id), mock_identifier_entry.entry_id
        )
        is not None
    )

    await hass.config_entries.async_setup(mock_identifier_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, mock_identifier_entry.entry_id), mock_identifier_entry.entry_id
        )
        is None
    )


async def test_load_entry_without_region_or_tracker(hass: HomeAssistant) -> None:
    """Test setup failure when neither a region nor a tracker is configured."""
    entry = await init_integration(hass, MockConfigEntry(domain=DOMAIN, data={}))

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_load_entry_with_invalid_api_data(
    hass: HomeAssistant,
    mock_identifier_entry: MockConfigEntry,
) -> None:
    """Test setup retry when the API returns invalid data."""
    entry = await init_integration(hass, mock_identifier_entry)

    assert entry.state is ConfigEntryState.SETUP_RETRY


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
    """Test loading the integration with a device tracker missing a required attr."""
    mock_tracker_entry.add_to_hass(hass)
    hass.states.async_set(
        mock_tracker_entry.data[CONF_REGION_DEVICE_TRACKER],
        STATE_HOME,
        {ATTR_LONGITUDE: 7.610263},
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
    mock_dwdwfsapi.data_valid = True
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
        {ATTR_LATITUDE: 50.180454, ATTR_LONGITUDE: 7.610263},
    )

    await hass.config_entries.async_setup(mock_tracker_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_tracker_entry.state is ConfigEntryState.LOADED
    assert isinstance(mock_tracker_entry.runtime_data, DwdWeatherWarningsCoordinator)


async def test_failed_device_tracker_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_tracker_entry: MockConfigEntry,
    mock_dwdwfsapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an API update failure for a device tracker entry."""
    mock_dwdwfsapi.data_valid = True
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
        {ATTR_LATITUDE: 50.180454, ATTR_LONGITUDE: 7.610263},
    )

    await hass.config_entries.async_setup(mock_tracker_entry.entry_id)
    await hass.async_block_till_done()

    def invalidate_api_data() -> None:
        mock_dwdwfsapi.data_valid = False

    mock_dwdwfsapi.update.reset_mock()
    mock_dwdwfsapi.update.side_effect = invalidate_api_data
    coordinator = mock_tracker_entry.runtime_data
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_dwdwfsapi.update.assert_called_once()
    assert isinstance(coordinator.last_exception, UpdateFailedUnreachable)
    assert coordinator.last_exception.translation_key == "cannot_connect"


async def test_device_tracker_missing_during_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_tracker_entry: MockConfigEntry,
    mock_dwdwfsapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an update failure when the tracker state disappears."""
    mock_dwdwfsapi.data_valid = True
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
        {ATTR_LATITUDE: 50.180454, ATTR_LONGITUDE: 7.610263},
    )

    await hass.config_entries.async_setup(mock_tracker_entry.entry_id)
    await hass.async_block_till_done()
    hass.states.async_remove(mock_tracker_entry.data[CONF_REGION_DEVICE_TRACKER])

    coordinator = mock_tracker_entry.runtime_data
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_key == "position_error"


async def test_device_tracker_moved(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_tracker_entry: MockConfigEntry,
    mock_dwdwfsapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test recreating the API when the device tracker moves."""
    mock_dwdwfsapi.data_valid = True
    mock_tracker_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "device_tracker",
        mock_tracker_entry.domain,
        "uuid",
        suggested_object_id="test_gps",
        config_entry=mock_tracker_entry,
    )
    tracker_id = mock_tracker_entry.data[CONF_REGION_DEVICE_TRACKER]
    hass.states.async_set(
        tracker_id,
        STATE_HOME,
        {ATTR_LATITUDE: 50.180454, ATTR_LONGITUDE: 7.610263},
    )

    await hass.config_entries.async_setup(mock_tracker_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        tracker_id,
        STATE_HOME,
        {ATTR_LATITUDE: 50.19, ATTR_LONGITUDE: 7.610263},
    )
    new_api = MagicMock()
    new_api.data_valid = True
    with patch(
        "homeassistant.components.dwd_weather_warnings.coordinator.DwdWeatherWarningsAPI",
        return_value=new_api,
    ) as mock_api:
        coordinator = mock_tracker_entry.runtime_data
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_api.assert_called_once()
    assert coordinator.api is new_api


async def test_filter_expired_warnings(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_dwdwfsapi: MagicMock,
    mock_identifier_entry: MockConfigEntry,
) -> None:
    """Test expired-warning filtering."""
    now = dt_util.utcnow()
    mock_dwdwfsapi.data_valid = True
    mock_dwdwfsapi.warncell_id = mock_identifier_entry.data[CONF_REGION_IDENTIFIER]
    mock_dwdwfsapi.warncell_name = "Test region"
    mock_dwdwfsapi.current_warnings = [
        _warning(4, now - timedelta(minutes=30)),
        _warning(2, now + timedelta(minutes=30)),
    ]
    mock_dwdwfsapi.expected_warnings = []

    await init_integration(hass, mock_identifier_entry)

    entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{mock_identifier_entry.unique_id}-{CURRENT_WARNING_SENSOR}",
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "2"
    assert state.attributes[ATTR_WARNING_COUNT] == 1
    assert "warning_2" not in state.attributes


async def test_no_warnings(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_dwdwfsapi: MagicMock,
    mock_identifier_entry: MockConfigEntry,
) -> None:
    """Test sensors when the API returns no warning data."""
    mock_dwdwfsapi.data_valid = True
    mock_dwdwfsapi.current_warnings = None
    mock_dwdwfsapi.expected_warnings = None

    await init_integration(hass, mock_identifier_entry)

    entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{mock_identifier_entry.unique_id}-{CURRENT_WARNING_SENSOR}",
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0"
    assert state.attributes[ATTR_WARNING_COUNT] == 0
