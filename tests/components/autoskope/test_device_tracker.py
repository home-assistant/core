"""Tests for the Autoskope device tracker."""

from datetime import UTC, datetime
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.autoskope.const import DOMAIN, MANUFACTURER
from homeassistant.components.autoskope.coordinator import (
    AutoskopeDataUpdateCoordinator,
)
from homeassistant.components.autoskope.models import (
    AutoskopeRuntimeData,
    Vehicle,
    VehiclePosition,
)
from homeassistant.components.device_tracker import SourceType
from homeassistant.config_entries import ConfigEntryState  # Import ConfigEntryState
from homeassistant.const import STATE_NOT_HOME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import MOCK_POSITION_FEATURE_1, MOCK_VEHICLE_INFO_1

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def mock_api() -> AsyncMock:
    """Return a mock Autoskope API instance."""
    api = AsyncMock()
    api.authenticate = AsyncMock(return_value=True)
    return api


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "test-user",
            "password": "test-pass",
            "host": "https://example.com",
        },
        entry_id="test-entry-id-123",
    )
    entry.add_to_hass(hass)
    return entry


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: AsyncMock,
    vehicles: list[Vehicle] | None = None,
) -> AutoskopeDataUpdateCoordinator:
    """Set up the Autoskope integration with mocked API data."""
    mock_api.get_vehicles.return_value = vehicles if vehicles is not None else []
    with patch(
        "homeassistant.components.autoskope.AutoskopeApi", return_value=mock_api
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the actual entry from hass after setup
    entry = hass.config_entries.async_get_entry(config_entry.entry_id)
    assert entry is not None
    assert entry.state is ConfigEntryState.LOADED

    # Assert runtime_data exists and get coordinator from it
    assert entry.runtime_data is not None
    runtime_data: AutoskopeRuntimeData = entry.runtime_data
    coordinator: AutoskopeDataUpdateCoordinator = runtime_data.coordinator

    assert coordinator is not None
    assert coordinator.last_update_success is True
    return coordinator


async def test_device_tracker(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test device tracker setup and state."""
    vehicle = Vehicle.from_api(
        MOCK_VEHICLE_INFO_1, {"features": [MOCK_POSITION_FEATURE_1]}
    )
    assert vehicle.position is not None
    coordinator = await setup_integration(hass, mock_config_entry, mock_api, [vehicle])
    assert coordinator.data
    assert vehicle.id in coordinator.data

    entity_registry = er.async_get(hass)
    # Use unique_id based on the entity implementation
    unique_id = f"{mock_config_entry.entry_id}_{vehicle.id}"
    entity_entry = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, unique_id
    )
    assert entity_entry is not None

    state = hass.states.get(entity_entry)
    assert state is not None
    # State should be 'not_home' as it has coordinates but isn't in 'home' zone
    assert state.state == STATE_NOT_HOME
    assert state.attributes.get("icon") == "mdi:car-clock"  # Based on park_mode=True
    assert isinstance(state.attributes, dict)
    assert state.attributes.get("latitude") == vehicle.position.latitude
    assert state.attributes.get("longitude") == vehicle.position.longitude
    assert state.attributes.get("source_type") == SourceType.GPS
    assert state.attributes.get("battery_voltage") == vehicle.battery_voltage
    assert state.attributes.get("external_voltage") == vehicle.external_voltage
    assert state.attributes.get("gps_quality") == vehicle.gps_quality
    assert state.attributes.get("speed") == vehicle.position.speed
    assert state.attributes.get("park_mode") == vehicle.position.park_mode
    assert state.attributes.get("last_update") == vehicle.position.timestamp
    assert state.attributes.get("imei") == vehicle.imei
    assert state.attributes.get("model") == vehicle.model
    # Adjust gps_accuracy assertion based on the actual calculation in device_tracker.py
    assert state.attributes.get("gps_accuracy") == max(1.0, vehicle.gps_quality * 5.0)
    assert state.attributes.get("activity") == "parked"


async def test_device_info_structure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: AsyncMock
) -> None:
    """Test the structure of device_info for trackers."""
    test_vehicle = Vehicle(
        id="test_id_dev_info",
        name="Test Device Info Vehicle",
        position=None,
        external_voltage=12.1,
        battery_voltage=4.2,
        gps_quality=0.9,
        imei="IMEI_DEV_INFO",
        model="ModelX",
    )
    await setup_integration(hass, mock_config_entry, mock_api, [test_vehicle])

    device_registry = dr.async_get(hass)
    # Device identifier is based on vehicle.id
    device = device_registry.async_get_device(identifiers={(DOMAIN, test_vehicle.id)})

    assert device is not None
    assert device.name == test_vehicle.name
    assert device.manufacturer == MANUFACTURER
    assert device.model == test_vehicle.model
    assert device.sw_version == test_vehicle.imei
    assert mock_config_entry.entry_id in device.config_entries


async def test_tracker_availability(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: AsyncMock
) -> None:
    """Test device tracker availability scenarios."""
    now_iso = datetime.now(UTC).isoformat()
    vehicle_with_pos = Vehicle(
        id="avail_1",
        name="Available",
        position=VehiclePosition(
            latitude=51.0, longitude=11.0, timestamp=now_iso, speed=0.0, park_mode=True
        ),
        external_voltage=12.2,
        battery_voltage=4.3,
        gps_quality=1.1,
        imei="IMEI_AVAIL1",
        model="ModelY",
    )
    vehicle_without_pos = Vehicle(
        id="avail_2",
        name="No Position",
        position=None,
        external_voltage=12.3,
        battery_voltage=4.4,
        gps_quality=1.2,
        imei="IMEI_AVAIL2",
        model="ModelZ",
    )
    coordinator = await setup_integration(
        hass, mock_config_entry, mock_api, [vehicle_with_pos, vehicle_without_pos]
    )
    entity_registry = er.async_get(hass)

    unique_id_with_pos = f"{mock_config_entry.entry_id}_{vehicle_with_pos.id}"
    unique_id_without_pos = f"{mock_config_entry.entry_id}_{vehicle_without_pos.id}"

    entity_with_pos_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, unique_id_with_pos
    )
    entity_without_pos_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, unique_id_without_pos
    )
    assert entity_with_pos_id is not None
    assert entity_without_pos_id is not None

    state_with_pos = hass.states.get(entity_with_pos_id)
    state_without_pos = hass.states.get(entity_without_pos_id)

    assert state_with_pos is not None
    assert state_with_pos.state == STATE_NOT_HOME
    assert state_with_pos.attributes.get("latitude") is not None
    assert state_with_pos.attributes.get("activity") == "parked"

    assert state_without_pos is not None
    assert state_without_pos.state == STATE_UNKNOWN
    assert state_without_pos.attributes.get("latitude") is None
    assert state_without_pos.attributes.get("activity") == "unknown"

    coordinator.last_update_success = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state_with_pos = hass.states.get(entity_with_pos_id)
    state_without_pos = hass.states.get(entity_without_pos_id)
    assert state_with_pos is not None
    assert state_with_pos.state == STATE_UNAVAILABLE
    assert state_without_pos is not None
    assert state_without_pos.state == STATE_UNAVAILABLE

    coordinator.last_update_success = True
    coordinator.async_set_updated_data(
        {
            vehicle_with_pos.id: vehicle_with_pos,
            vehicle_without_pos.id: vehicle_without_pos,
        }
    )
    await hass.async_block_till_done()

    state_with_pos = hass.states.get(entity_with_pos_id)
    state_without_pos = hass.states.get(entity_without_pos_id)
    assert state_with_pos is not None
    assert state_with_pos.state == STATE_NOT_HOME
    assert state_without_pos is not None
    assert state_without_pos.state == STATE_UNKNOWN
    assert state_without_pos.attributes.get("latitude") is None


async def test_tracker_state_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test device tracker state updates based on coordinator."""
    vehicle_id = "update_test_123"
    initial_vehicle = Vehicle(
        id=vehicle_id,
        name="Update Test Vehicle",
        position=VehiclePosition(
            latitude=10.0,
            longitude=20.0,
            timestamp="2023-01-01T10:00:00Z",
            speed=0.0,
            park_mode=True,
        ),
        external_voltage=12.5,
        battery_voltage=4.1,
        gps_quality=0.9,
        imei="IMEI_UPDATE",
        model="ModelU",
    )
    coordinator = await setup_integration(
        hass, mock_config_entry, mock_api, [initial_vehicle]
    )
    entity_registry = er.async_get(hass)
    unique_id = f"{mock_config_entry.entry_id}_{vehicle_id}"
    entity_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, unique_id)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert state.attributes.get("icon") == "mdi:car-clock"
    assert state.attributes.get("latitude") == 10.0
    assert state.attributes.get("longitude") == 20.0
    assert state.attributes.get("speed") == 0.0
    assert state.attributes.get("activity") == "parked"

    updated_vehicle = Vehicle(
        id=vehicle_id,
        name="Update Test Vehicle",
        position=VehiclePosition(
            latitude=10.1,
            longitude=20.1,
            timestamp="2023-01-01T10:05:00Z",
            speed=50.0,
            park_mode=False,
        ),
        external_voltage=12.4,
        battery_voltage=4.0,
        gps_quality=0.8,
        imei="IMEI_UPDATE",
        model="ModelU",
    )
    coordinator.async_set_updated_data({vehicle_id: updated_vehicle})
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert state.attributes.get("icon") == "mdi:car-arrow-right"
    assert state.attributes.get("latitude") == 10.1
    assert state.attributes.get("longitude") == 20.1
    assert state.attributes.get("speed") == 50.0
    assert state.attributes.get("park_mode") is False
    assert state.attributes.get("external_voltage") == 12.4
    assert state.attributes.get("activity") == "moving"


async def test_tracker_attributes_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test handling of attributes when data is missing or incomplete."""
    vehicle_id = "attr_test_456"
    vehicle_missing_attrs = Vehicle(
        id=vehicle_id,
        name="Attribute Test Vehicle",
        position=VehiclePosition(
            latitude=30.0,
            longitude=40.0,
            timestamp="2023-01-01T11:00:00Z",
            speed=10.0,
            park_mode=False,
        ),
        external_voltage=None,
        battery_voltage=None,
        gps_quality=None,
        imei="IMEI_ATTR",
        model="ModelA",
    )
    coordinator = await setup_integration(
        hass, mock_config_entry, mock_api, [vehicle_missing_attrs]
    )
    entity_registry = er.async_get(hass)
    unique_id = f"{mock_config_entry.entry_id}_{vehicle_id}"
    entity_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, unique_id)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert isinstance(state.attributes, dict)
    assert state.attributes.get("latitude") == 30.0
    assert state.attributes.get("external_voltage") is None
    assert state.attributes.get("battery_voltage") is None
    assert state.attributes.get("gps_quality") is None
    assert state.attributes.get("gps_accuracy") is None
    assert state.attributes.get("activity") == "moving"

    coordinator.async_set_updated_data({})
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert isinstance(state.attributes, dict)
    assert state.attributes.get("latitude") is None
    assert state.attributes.get("activity") is None


async def test_tracker_becomes_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test device tracker becomes unavailable when coordinator loses data for it."""
    vehicle_id = "unavail_test_789"
    initial_vehicle = Vehicle(
        id=vehicle_id,
        name="Unavailable Test Vehicle",
        position=VehiclePosition(
            latitude=50.0,
            longitude=5.0,
            timestamp="2023-01-01T12:00:00Z",
            speed=0.0,
            park_mode=True,
        ),
        external_voltage=12.5,
        battery_voltage=4.1,
        gps_quality=0.9,
        imei="IMEI_UNAVAIL",
        model="ModelUn",
    )
    coordinator = await setup_integration(
        hass, mock_config_entry, mock_api, [initial_vehicle]
    )
    entity_registry = er.async_get(hass)
    unique_id = f"{mock_config_entry.entry_id}_{vehicle_id}"
    entity_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, unique_id)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert state.attributes.get("activity") == "parked"

    coordinator.async_set_updated_data({})
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert isinstance(state.attributes, dict)
    assert state.attributes.get("latitude") is None
    assert state.attributes.get("longitude") is None
    assert state.attributes.get("last_update") is None
    assert state.attributes.get("battery_voltage") is None
    assert state.attributes.get("activity") is None


async def test_gps_accuracy(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test gps_accuracy calculation."""
    vehicle_id_base = "gps_acc_test"
    vehicles = [
        Vehicle(
            id=f"{vehicle_id_base}_1",
            name="GPS Acc 1",
            position=MagicMock(latitude=50.0, longitude=10.0),
            external_voltage=12,
            battery_voltage=4,
            gps_quality=1.5,
            imei="I1",
            model="M1",
        ),
        Vehicle(
            id=f"{vehicle_id_base}_2",
            name="GPS Acc 2",
            position=MagicMock(latitude=50.0, longitude=10.0),
            external_voltage=12,
            battery_voltage=4,
            gps_quality=0.4,
            imei="I2",
            model="M2",
        ),
        Vehicle(
            id=f"{vehicle_id_base}_3",
            name="GPS Acc 3",
            position=MagicMock(latitude=50.0, longitude=10.0),
            external_voltage=12,
            battery_voltage=4,
            gps_quality=0.0,
            imei="I3",
            model="M3",
        ),
        Vehicle(
            id=f"{vehicle_id_base}_4",
            name="GPS Acc 4",
            position=MagicMock(latitude=50.0, longitude=10.0),
            external_voltage=12,
            battery_voltage=4,
            gps_quality=None,
            imei="I4",
            model="M4",
        ),
    ]
    await setup_integration(hass, mock_config_entry, mock_api, vehicles)
    entity_registry = er.async_get(hass)

    unique_id_1 = f"{mock_config_entry.entry_id}_{vehicle_id_base}_1"
    unique_id_2 = f"{mock_config_entry.entry_id}_{vehicle_id_base}_2"
    unique_id_3 = f"{mock_config_entry.entry_id}_{vehicle_id_base}_3"
    unique_id_4 = f"{mock_config_entry.entry_id}_{vehicle_id_base}_4"

    state1 = hass.states.get(
        entity_registry.async_get_entity_id("device_tracker", DOMAIN, unique_id_1)
    )
    assert state1 and state1.attributes.get("gps_accuracy") == 7.5

    state2 = hass.states.get(
        entity_registry.async_get_entity_id("device_tracker", DOMAIN, unique_id_2)
    )
    assert state2 and state2.attributes.get("gps_accuracy") == 2.0

    state3 = hass.states.get(
        entity_registry.async_get_entity_id("device_tracker", DOMAIN, unique_id_3)
    )
    assert state3 and state3.attributes.get("gps_accuracy") is None

    state4 = hass.states.get(
        entity_registry.async_get_entity_id("device_tracker", DOMAIN, unique_id_4)
    )
    assert state4 and state4.attributes.get("gps_accuracy") is None


async def test_state_activity_and_icon(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test state, activity attribute, and icon based on park_mode and speed."""
    vehicle_id_base = "state_icon_test"
    now_iso = datetime.now(UTC).isoformat()
    vehicles = [
        Vehicle(
            id=f"{vehicle_id_base}_1",
            name="Parked 1",
            position=VehiclePosition(
                latitude=1, longitude=1, timestamp=now_iso, speed=0.0, park_mode=True
            ),
            external_voltage=12,
            battery_voltage=4,
            gps_quality=1,
            imei="I1",
            model="M1",
        ),
        Vehicle(
            id=f"{vehicle_id_base}_2",
            name="Parked 2",
            position=VehiclePosition(
                latitude=2, longitude=2, timestamp=now_iso, speed=5.0, park_mode=True
            ),
            external_voltage=12,
            battery_voltage=4,
            gps_quality=1,
            imei="I2",
            model="M2",
        ),
        Vehicle(
            id=f"{vehicle_id_base}_3",
            name="Moving 1",
            position=VehiclePosition(
                latitude=3, longitude=3, timestamp=now_iso, speed=10.0, park_mode=False
            ),
            external_voltage=12,
            battery_voltage=4,
            gps_quality=1,
            imei="I3",
            model="M3",
        ),
        Vehicle(
            id=f"{vehicle_id_base}_4",
            name="Stopped",
            position=VehiclePosition(
                latitude=4, longitude=4, timestamp=now_iso, speed=0.0, park_mode=False
            ),
            external_voltage=12,
            battery_voltage=4,
            gps_quality=1,
            imei="I4",
            model="M4",
        ),
        Vehicle(
            id=f"{vehicle_id_base}_5",
            name="No Pos",
            position=None,
            external_voltage=12,
            battery_voltage=4,
            gps_quality=1,
            imei="I5",
            model="M5",
        ),
    ]
    await setup_integration(hass, mock_config_entry, mock_api, vehicles)
    entity_registry = er.async_get(hass)

    unique_id_1 = f"{mock_config_entry.entry_id}_{vehicle_id_base}_1"
    state1 = hass.states.get(
        entity_registry.async_get_entity_id("device_tracker", DOMAIN, unique_id_1)
    )
    assert state1 and state1.state == STATE_NOT_HOME
    assert state1 and state1.attributes.get("icon") == "mdi:car-clock"
    assert state1 and state1.attributes.get("activity") == "parked"

    unique_id_2 = f"{mock_config_entry.entry_id}_{vehicle_id_base}_2"
    state2 = hass.states.get(
        entity_registry.async_get_entity_id("device_tracker", DOMAIN, unique_id_2)
    )
    assert state2 and state2.state == STATE_NOT_HOME
    assert state2 and state2.attributes.get("icon") == "mdi:car-clock"
    assert state2 and state2.attributes.get("activity") == "parked"

    unique_id_3 = f"{mock_config_entry.entry_id}_{vehicle_id_base}_3"
    state3 = hass.states.get(
        entity_registry.async_get_entity_id("device_tracker", DOMAIN, unique_id_3)
    )
    assert state3 and state3.state == STATE_NOT_HOME
    assert state3 and state3.attributes.get("icon") == "mdi:car-arrow-right"
    assert state3 and state3.attributes.get("activity") == "moving"

    unique_id_4 = f"{mock_config_entry.entry_id}_{vehicle_id_base}_4"
    state4 = hass.states.get(
        entity_registry.async_get_entity_id("device_tracker", DOMAIN, unique_id_4)
    )
    assert state4 and state4.state == STATE_NOT_HOME
    assert state4 and state4.attributes.get("icon") == "mdi:car-clock"
    assert state4 and state4.attributes.get("activity") == "parked"

    unique_id_5 = f"{mock_config_entry.entry_id}_{vehicle_id_base}_5"
    state5 = hass.states.get(
        entity_registry.async_get_entity_id("device_tracker", DOMAIN, unique_id_5)
    )
    assert state5 and state5.state == STATE_UNKNOWN
    assert state5 and state5.attributes.get("icon") == "mdi:car-clock"
    assert state5 and state5.attributes.get("activity") == "unknown"
