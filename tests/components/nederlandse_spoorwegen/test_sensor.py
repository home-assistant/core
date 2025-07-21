"""Test the Nederlandse Spoorwegen sensor logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.nederlandse_spoorwegen import DOMAIN, NSRuntimeData
from homeassistant.components.nederlandse_spoorwegen.coordinator import (
    NSDataUpdateCoordinator,
)
from homeassistant.components.nederlandse_spoorwegen.sensor import (
    NEXT_DEPARTURE_DESCRIPTION,
    SENSOR_DESCRIPTIONS,
    NSNextDepartureSensor,
    NSSensor,
    async_setup_entry,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def mock_nsapi():
    """Mock NSAPI client."""
    nsapi = MagicMock()
    nsapi.get_stations.return_value = [MagicMock(code="AMS"), MagicMock(code="UTR")]
    nsapi.get_trips.return_value = []
    return nsapi


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {CONF_API_KEY: "test_api_key"}
    entry.options = {"routes": []}
    entry.subentries = {}
    return entry


@pytest.fixture
def mock_coordinator(mock_config_entry, mock_nsapi):
    """Mock coordinator."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock()

    coordinator = NSDataUpdateCoordinator(hass, mock_nsapi, mock_config_entry)
    coordinator.data = {
        "routes": {},
        "stations": [MagicMock(code="AMS"), MagicMock(code="UTR")],
    }
    return coordinator


async def test_async_setup_entry_no_routes(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test setup entry with no routes configured."""
    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = NSRuntimeData(coordinator=mock_coordinator)

    # Mock coordinator data with no routes
    mock_coordinator.data = {"routes": {}, "stations": []}

    entities = []

    def mock_add_entities(
        new_entities, update_before_add=False, *, config_subentry_id=None
    ):
        entities.extend(new_entities)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    # Should create no sensors (new architecture: no main entry sensors)
    assert len(entities) == 0


async def test_async_setup_entry_with_routes(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test setup entry with routes configured."""
    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = NSRuntimeData(coordinator=mock_coordinator)

    # Mock coordinator data with routes
    mock_coordinator.data = {
        "routes": {
            "Test Route_AMS_UTR": {
                "route": {"name": "Test Route", "from": "AMS", "to": "UTR"}
            },
            "Another Route_RTD_GVC": {
                "route": {"name": "Another Route", "from": "RTD", "to": "GVC"}
            },
        },
        "stations": [],
    }

    entities = []

    def mock_add_entities(
        new_entities, update_before_add=False, *, config_subentry_id=None
    ):
        entities.extend(new_entities)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    # Should create no sensors (new architecture: no main entry sensors, only subentry sensors)
    assert len(entities) == 0


async def test_async_setup_entry_no_coordinator_data(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test setup entry when coordinator has no data yet."""
    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = NSRuntimeData(coordinator=mock_coordinator)

    # Mock coordinator with no data
    mock_coordinator.data = None

    entities = []

    def mock_add_entities(
        new_entities, update_before_add=False, *, config_subentry_id=None
    ):
        entities.extend(new_entities)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    # Should create no sensors (new architecture: no main entry sensors)
    assert len(entities) == 0


async def test_device_association_after_migration(hass: HomeAssistant) -> None:
    """Test that sensors are created under subentries, not main integration."""
    with (
        patch(
            "homeassistant.components.nederlandse_spoorwegen.NSAPIWrapper"
        ) as mock_api_wrapper_class,
        patch(
            "homeassistant.components.nederlandse_spoorwegen.NSAPIWrapper.normalize_station_code",
            side_effect=lambda code: code.upper() if code else "",
        ),
    ):
        # Mock stations with required station codes
        mock_station_asd = type(
            "Station", (), {"code": "ASD", "name": "Amsterdam Centraal"}
        )()
        mock_station_rtd = type(
            "Station", (), {"code": "RTD", "name": "Rotterdam Centraal"}
        )()

        # Set up the mock API wrapper
        mock_api_wrapper = MagicMock()
        # Make async methods async
        mock_api_wrapper.get_stations = AsyncMock(
            return_value=[
                mock_station_asd,
                mock_station_rtd,
            ]
        )
        mock_api_wrapper.get_trips = AsyncMock(return_value=[])
        mock_api_wrapper.validate_api_key = AsyncMock(return_value=None)
        # Mock the get_station_codes as a regular method (not async)
        mock_api_wrapper.get_station_codes = MagicMock(return_value={"ASD", "RTD"})
        # Mock the normalize_station_code method as regular method
        mock_api_wrapper.normalize_station_code = MagicMock(
            side_effect=lambda code: code.upper() if code else ""
        )
        mock_api_wrapper_class.return_value = mock_api_wrapper

        # Create config entry with legacy routes
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                "api_key": "test_key",
                "routes": [
                    {
                        "name": "Test Route",
                        "from": "ASD",
                        "to": "RTD",
                    },
                ],
            },
        )
        config_entry.add_to_hass(hass)

        # Setup the integration
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Get registries
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)

        # Check that migration created subentries
        assert len(config_entry.subentries) == 1
        subentry = next(iter(config_entry.subentries.values()))

        # Find all devices
        devices = list(device_registry.devices.values())

        main_devices = [
            device
            for device in devices
            if (DOMAIN, config_entry.entry_id) in device.identifiers
        ]

        subentry_devices = [
            device
            for device in devices
            if any(
                identifier[0] == DOMAIN and identifier[1] == subentry.subentry_id
                for identifier in device.identifiers
            )
        ]

        # Should have 0 main devices (no entities created under main integration)
        assert len(main_devices) == 0, (
            f"Expected 0 main devices, got {len(main_devices)}"
        )

        # Should have 1 subentry device (route sensor creates its own device)
        assert len(subentry_devices) == 1, (
            f"Expected 1 subentry device, got {len(subentry_devices)}"
        )

        # Find all entities
        entities = list(entity_registry.entities.values())

        main_entities = [
            entity
            for entity in entities
            if entity.config_entry_id == config_entry.entry_id
            and entity.config_subentry_id is None
        ]

        subentry_entities = [
            entity
            for entity in entities
            if entity.config_entry_id == config_entry.entry_id
            and entity.config_subentry_id is not None
        ]

        # Should have 0 main entities: no sensors under main integration
        assert len(main_entities) == 0, (
            f"Expected 0 main entities, got {len(main_entities)}"
        )

        # Should have 14 subentry entities (14 attribute sensors, no main trip sensor)
        assert len(subentry_entities) == 14, (
            f"Expected 14 subentry entities, got {len(subentry_entities)}"
        )

        # Verify we have all the expected sensors
        subentry_entity_ids = {entity.entity_id for entity in subentry_entities}
        expected_entities = {
            "sensor.test_route_departure_platform_planned",
            "sensor.test_route_departure_platform_actual",
            "sensor.test_route_arrival_platform_planned",
            "sensor.test_route_arrival_platform_actual",
            "sensor.test_route_departure_time_planned",
            "sensor.test_route_departure_time_actual",
            "sensor.test_route_arrival_time_planned",
            "sensor.test_route_arrival_time_actual",
            "sensor.test_route_next_departure",
            "sensor.test_route_status",
            "sensor.test_route_transfers",
            "sensor.test_route_route_from",
            "sensor.test_route_route_to",
            "sensor.test_route_route_via",
        }
        assert subentry_entity_ids == expected_entities

        # Verify the subentry device has the route information
        subentry_device = subentry_devices[0]
        assert subentry_device.name == "Test Route"
        assert subentry_device.manufacturer == "Nederlandse Spoorwegen"

        # Unload entry
        assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_async_setup_entry_no_coordinator(hass: HomeAssistant) -> None:
    """Test setup entry when coordinator is None (missing coverage line 158-159)."""
    mock_config_entry = MagicMock()
    mock_config_entry.entry_id = "test_entry"
    mock_config_entry.subentries = {}

    # Create a mock coordinator for NSRuntimeData
    mock_coordinator = MagicMock()
    mock_config_entry.runtime_data = NSRuntimeData(coordinator=mock_coordinator)

    # Then set the coordinator to None to trigger the error path
    mock_config_entry.runtime_data.coordinator = None

    entities = []

    def mock_add_entities(
        new_entities, update_before_add=False, *, config_subentry_id=None
    ):
        entities.extend(new_entities)

    # This should trigger the error path on lines 158-159
    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    # Should create no sensors when coordinator is None
    assert len(entities) == 0


async def test_sensor_device_info_legacy_route(hass: HomeAssistant) -> None:
    """Test sensor device info creation for legacy routes (coverage lines 249, 284-285)."""
    mock_config_entry = MagicMock()
    mock_config_entry.entry_id = "test_entry"
    mock_coordinator = MagicMock()

    # Create a route without subentry (legacy route)
    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"
    description = SENSOR_DESCRIPTIONS[0]  # Use first description

    # Create sensor without subentry_id to trigger legacy device logic
    sensor = NSSensor(
        coordinator=mock_coordinator,
        entry=mock_config_entry,
        route=route,
        route_key=route_key,
        description=description,
    )

    # Test device info for legacy route (lines 249, 284-285)
    device_info = sensor.device_info
    assert device_info is not None
    assert device_info.get("identifiers") is not None
    assert (DOMAIN, mock_config_entry.entry_id) in device_info["identifiers"]


async def test_sensor_available_property_coordinator_data_none(
    hass: HomeAssistant,
) -> None:
    """Test sensor availability when coordinator data is None (coverage line 264)."""
    mock_config_entry = MagicMock()
    mock_config_entry.entry_id = "test_entry"
    mock_coordinator = MagicMock()
    mock_coordinator.data = None  # This triggers line 264
    mock_coordinator.last_update_success = True

    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"
    description = SENSOR_DESCRIPTIONS[0]

    sensor = NSSensor(
        coordinator=mock_coordinator,
        entry=mock_config_entry,
        route=route,
        route_key=route_key,
        description=description,
    )

    # Should be unavailable when coordinator.data is None
    assert not sensor.available


async def test_sensor_available_property_route_not_in_data(hass: HomeAssistant) -> None:
    """Test sensor availability when route key not in coordinator data (coverage line 264)."""
    mock_config_entry = MagicMock()
    mock_config_entry.entry_id = "test_entry"
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"routes": {}}  # Empty routes dict
    mock_coordinator.last_update_success = True

    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"
    description = SENSOR_DESCRIPTIONS[0]

    sensor = NSSensor(
        coordinator=mock_coordinator,
        entry=mock_config_entry,
        route=route,
        route_key=route_key,
        description=description,
    )

    # Should be unavailable when route key not in data
    assert not sensor.available


async def test_sensor_native_value_no_coordinator_data(hass: HomeAssistant) -> None:
    """Test sensor native value when coordinator data is None (coverage line 274)."""
    mock_config_entry = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.data = None  # This triggers line 274

    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"
    description = SENSOR_DESCRIPTIONS[0]

    sensor = NSSensor(
        coordinator=mock_coordinator,
        entry=mock_config_entry,
        route=route,
        route_key=route_key,
        description=description,
    )

    # Should return None when coordinator data is None
    assert sensor.native_value is None


async def test_sensor_native_value_no_value_fn(hass: HomeAssistant) -> None:
    """Test sensor native value when description has no value_fn (coverage line 274)."""
    mock_config_entry = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"routes": {"Test Route_AMS_UTR": {}}}

    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"

    # Create description without value_fn
    description = MagicMock()
    description.key = "test"
    description.value_fn = None  # This triggers line 274

    sensor = NSSensor(
        coordinator=mock_coordinator,
        entry=mock_config_entry,
        route=route,
        route_key=route_key,
        description=description,
    )

    # Should return None when value_fn is None
    assert sensor.native_value is None


async def test_sensor_native_value_invalid_routes_data(hass: HomeAssistant) -> None:
    """Test sensor native value with invalid routes data structure (coverage lines 279-280)."""
    mock_config_entry = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"routes": "invalid_data"}  # Not a dict

    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"
    description = SENSOR_DESCRIPTIONS[0]

    sensor = NSSensor(
        coordinator=mock_coordinator,
        entry=mock_config_entry,
        route=route,
        route_key=route_key,
        description=description,
    )

    # Should return None when routes data is invalid
    assert sensor.native_value is None


async def test_sensor_native_value_invalid_route_specific_data(
    hass: HomeAssistant,
) -> None:
    """Test sensor native value with invalid route-specific data (coverage lines 291-295)."""
    mock_config_entry = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.data = {
        "routes": {"Test Route_AMS_UTR": "invalid_route_data"}  # Not a dict
    }

    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"
    description = SENSOR_DESCRIPTIONS[0]

    sensor = NSSensor(
        coordinator=mock_coordinator,
        entry=mock_config_entry,
        route=route,
        route_key=route_key,
        description=description,
    )

    # Should return None when route-specific data is invalid
    assert sensor.native_value is None


async def test_sensor_native_value_exception_handling(hass: HomeAssistant) -> None:
    """Test sensor native value exception handling (coverage lines 305, TypeError/AttributeError/KeyError)."""
    mock_config_entry = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"routes": {"Test Route_AMS_UTR": {"first_trip": {}}}}

    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"

    # Create description with value_fn that raises exception
    description = MagicMock()
    description.key = "test"
    description.value_fn = MagicMock(side_effect=TypeError("Test error"))

    sensor = NSSensor(
        coordinator=mock_coordinator,
        entry=mock_config_entry,
        route=route,
        route_key=route_key,
        description=description,
    )

    # Should return None when value_fn raises exception
    assert sensor.native_value is None


async def test_next_departure_sensor_native_value_no_coordinator_data(
    hass: HomeAssistant,
) -> None:
    """Test next departure sensor native value when coordinator data is None (coverage line 310-311)."""
    mock_config_entry = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.data = None  # This triggers line 310-311

    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"

    sensor = NSNextDepartureSensor(
        coordinator=mock_coordinator,
        entry=mock_config_entry,
        route=route,
        route_key=route_key,
        description=NEXT_DEPARTURE_DESCRIPTION,
    )

    # Should return None when coordinator data is None
    assert sensor.native_value is None


async def test_next_departure_sensor_native_value_invalid_routes_data(
    hass: HomeAssistant,
) -> None:
    """Test next departure sensor with invalid routes data (coverage lines 315-316)."""
    mock_config_entry = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"routes": "invalid_data"}  # Not a dict

    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"

    sensor = NSNextDepartureSensor(
        coordinator=mock_coordinator,
        entry=mock_config_entry,
        route=route,
        route_key=route_key,
        description=NEXT_DEPARTURE_DESCRIPTION,
    )

    # Should return None when routes data is invalid
    assert sensor.native_value is None


async def test_next_departure_sensor_native_value_exception_handling(
    hass: HomeAssistant,
) -> None:
    """Test next departure sensor exception handling (coverage lines 322-324)."""
    mock_config_entry = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"routes": {"Test Route_AMS_UTR": {"next_trip": {}}}}

    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"

    # Create description with value_fn that raises exception
    description = MagicMock()
    description.key = "next_departure"
    description.value_fn = MagicMock(side_effect=KeyError("Test error"))

    sensor = NSNextDepartureSensor(
        coordinator=mock_coordinator,
        entry=mock_config_entry,
        route=route,
        route_key=route_key,
        description=description,
    )

    # Should return None when value_fn raises exception
    assert sensor.native_value is None


async def test_next_departure_sensor_invalid_route_specific_data(
    hass: HomeAssistant,
) -> None:
    """Test next departure sensor with invalid route-specific data (coverage lines 315-316)."""
    mock_config_entry = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.data = {
        "routes": {"Test Route_AMS_UTR": "invalid_route_data"}  # Not a dict
    }

    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"

    sensor = NSNextDepartureSensor(
        coordinator=mock_coordinator,
        entry=mock_config_entry,
        route=route,
        route_key=route_key,
        description=NEXT_DEPARTURE_DESCRIPTION,
    )

    # Should return None when route-specific data is invalid
    assert sensor.native_value is None
