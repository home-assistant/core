"""Test the Nederlandse Spoorwegen sensor logic."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.nederlandse_spoorwegen import DOMAIN
from homeassistant.components.nederlandse_spoorwegen.coordinator import (
    NSDataUpdateCoordinator,
)
from homeassistant.components.nederlandse_spoorwegen.sensor import (
    NSServiceSensor,
    NSTripSensor,
    async_setup_entry,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant


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


def test_service_sensor_creation(mock_coordinator, mock_config_entry) -> None:
    """Test NSServiceSensor creation."""
    sensor = NSServiceSensor(mock_coordinator, mock_config_entry)

    assert sensor.unique_id == "test_entry_id_service"
    assert sensor.translation_key == "service"
    assert sensor.device_info is not None


def test_service_sensor_native_value_no_routes(
    mock_coordinator, mock_config_entry
) -> None:
    """Test service sensor value with no routes."""
    mock_coordinator.data = {"routes": {}, "stations": []}
    sensor = NSServiceSensor(mock_coordinator, mock_config_entry)

    assert sensor.native_value == "no_routes"


def test_service_sensor_native_value_with_routes(
    mock_coordinator, mock_config_entry
) -> None:
    """Test service sensor value with routes that have data."""
    mock_coordinator.data = {
        "routes": {
            "test_route": {
                "trips": [MagicMock()],
                "route": {"name": "Test", "from": "AMS", "to": "UTR"},
            }
        },
        "stations": [],
    }
    sensor = NSServiceSensor(mock_coordinator, mock_config_entry)

    assert sensor.native_value == "connected"


def test_trip_sensor_creation(mock_coordinator, mock_config_entry) -> None:
    """Test NSTripSensor creation."""
    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, "test_route_key")

    assert sensor.unique_id == "test_entry_id_test_route_key"
    assert sensor.name == "Test Route"
    assert sensor.device_info is not None


def test_trip_sensor_available_no_data(mock_coordinator, mock_config_entry) -> None:
    """Test trip sensor availability when no data is available."""
    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, "test_route_key")

    # Mock coordinator.available to True but no route data
    mock_coordinator.available = True
    mock_coordinator.data = {"routes": {}}

    assert not sensor.available


def test_trip_sensor_native_value_no_trip(mock_coordinator, mock_config_entry) -> None:
    """Test trip sensor value when no trip data is available."""
    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, "test_route_key")

    mock_coordinator.data = {
        "routes": {
            "test_route_key": {
                "route": route,
                "trips": [],
                "first_trip": None,
                "next_trip": None,
            }
        }
    }

    assert sensor.native_value == "no_trip"


def test_trip_sensor_extra_state_attributes(
    mock_coordinator, mock_config_entry
) -> None:
    """Test trip sensor extra state attributes."""
    route = {"name": "Test Route", "from": "AMS", "to": "UTR", "via": "ASS"}
    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, "test_route_key")

    mock_coordinator.data = {
        "routes": {
            "test_route_key": {
                "route": route,
                "trips": [],
                "first_trip": None,
                "next_trip": None,
            }
        }
    }

    attributes = sensor.extra_state_attributes
    assert attributes["route_from"] == "AMS"
    assert attributes["route_to"] == "UTR"
    assert attributes["route_via"] == "ASS"


async def test_async_setup_entry_no_routes(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test setup entry with no routes configured."""
    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = {"coordinator": mock_coordinator}

    # Mock coordinator data with no routes
    mock_coordinator.data = {"routes": {}, "stations": []}

    entities = []

    def mock_add_entities(
        new_entities, update_before_add=False, *, config_subentry_id=None
    ):
        entities.extend(new_entities)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    # Should create only the service sensor
    assert len(entities) == 1
    assert isinstance(entities[0], NSServiceSensor)


async def test_async_setup_entry_with_routes(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test setup entry with routes configured."""
    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = {"coordinator": mock_coordinator}

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

    # Should create service sensor + 2 trip sensors
    assert len(entities) == 3
    assert isinstance(entities[0], NSServiceSensor)
    assert isinstance(entities[1], NSTripSensor)
    assert isinstance(entities[2], NSTripSensor)


async def test_async_setup_entry_no_coordinator_data(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test setup entry when coordinator has no data yet."""
    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = {"coordinator": mock_coordinator}

    # Mock coordinator with no data
    mock_coordinator.data = None

    entities = []

    def mock_add_entities(
        new_entities, update_before_add=False, *, config_subentry_id=None
    ):
        entities.extend(new_entities)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    # Should create only the service sensor
    assert len(entities) == 1
    assert isinstance(entities[0], NSServiceSensor)


def test_service_sensor_device_info(mock_coordinator) -> None:
    """Test service sensor device info."""
    mock_config_entry = MagicMock()
    mock_config_entry.entry_id = "test_entry_id"
    mock_config_entry.title = "Nederlandse Spoorwegen"
    sensor = NSServiceSensor(mock_coordinator, mock_config_entry)
    device_info = sensor.device_info
    assert device_info is not None
    assert "identifiers" in device_info
    assert device_info["identifiers"] == {(DOMAIN, "test_entry_id")}
    assert device_info.get("name") == "Nederlandse Spoorwegen"
    assert device_info.get("manufacturer") == "Nederlandse Spoorwegen"


def test_service_sensor_device_info_dict(mock_coordinator, mock_config_entry) -> None:
    """Test service sensor device_info is a DeviceInfo and has correct fields."""
    sensor = NSServiceSensor(mock_coordinator, mock_config_entry)
    device_info = sensor.device_info
    assert device_info is not None
    assert "identifiers" in device_info
    assert device_info["identifiers"] == {(DOMAIN, "test_entry_id")}
    assert device_info.get("name") == "Nederlandse Spoorwegen"
    assert device_info.get("manufacturer") == "Nederlandse Spoorwegen"
    assert device_info.get("model") == "NS API"
    assert device_info.get("sw_version") == "1.0"
    assert device_info.get("configuration_url") == "https://www.ns.nl/"


def test_trip_sensor_device_info(mock_coordinator) -> None:
    """Test trip sensor device info."""
    mock_config_entry = MagicMock()
    mock_config_entry.entry_id = "test_entry_id"

    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"

    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, route_key)

    device_info = sensor.device_info
    assert device_info is not None
    assert "identifiers" in device_info
    assert device_info["identifiers"] == {(DOMAIN, "test_entry_id")}


def test_trip_sensor_device_info_dict(mock_coordinator, mock_config_entry) -> None:
    """Test trip sensor device_info is a DeviceInfo and has correct fields."""
    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"
    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, route_key)
    device_info = sensor.device_info
    assert device_info is not None
    assert "identifiers" in device_info
    assert device_info["identifiers"] == {(DOMAIN, mock_config_entry.entry_id)}


async def test_service_sensor_extra_state_attributes_no_data(mock_coordinator) -> None:
    """Test service sensor extra state attributes when no data."""
    mock_config_entry = MagicMock()
    mock_coordinator.data = None

    sensor = NSServiceSensor(mock_coordinator, mock_config_entry)

    attributes = sensor.extra_state_attributes
    assert attributes == {}


async def test_service_sensor_extra_state_attributes_with_data(
    mock_coordinator,
) -> None:
    """Test service sensor extra state attributes with data."""
    mock_config_entry = MagicMock()
    mock_coordinator.data = {
        "routes": {"route1": {}, "route2": {}},
        "stations": [{"code": "AMS"}, {"code": "UTR"}, {"code": "RTD"}],
    }

    sensor = NSServiceSensor(mock_coordinator, mock_config_entry)

    attributes = sensor.extra_state_attributes
    assert attributes == {"total_routes": 2, "active_routes": 0}


def test_service_sensor_extra_state_attributes_empty(
    mock_coordinator, mock_config_entry
) -> None:
    """Test service sensor extra_state_attributes returns empty dict when no data."""
    mock_coordinator.data = None
    sensor = NSServiceSensor(mock_coordinator, mock_config_entry)
    attrs = sensor.extra_state_attributes
    assert attrs == {}


def test_service_sensor_extra_state_attributes_partial(
    mock_coordinator, mock_config_entry
) -> None:
    """Test service sensor extra_state_attributes with only routes present."""
    mock_coordinator.data = {"routes": {"r1": {}}, "stations": None}
    sensor = NSServiceSensor(mock_coordinator, mock_config_entry)
    attrs = sensor.extra_state_attributes
    assert attrs["total_routes"] == 1
    assert attrs["active_routes"] == 0


def test_trip_sensor_name_translation(mock_coordinator) -> None:
    """Test trip sensor translation_key is None (not set in code)."""
    mock_config_entry = MagicMock()
    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"
    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, route_key)
    assert getattr(sensor, "translation_key", None) is None


def test_trip_sensor_extra_state_attributes_no_trips(mock_coordinator) -> None:
    """Test trip sensor attributes when no trips available."""
    mock_config_entry = MagicMock()
    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"

    # Mock coordinator data with no trips
    mock_coordinator.data = {
        "routes": {
            route_key: {
                "route": route,
                "trips": [],
                "first_trip": None,
                "next_trip": None,
            }
        }
    }

    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, route_key)

    attributes = sensor.extra_state_attributes
    assert attributes == {"route_from": "AMS", "route_to": "UTR", "route_via": None}


# Additional test for uncovered lines (unknown native_value, disconnected state, etc)
def test_service_sensor_native_value_unknown_and_disconnected(
    mock_coordinator, mock_config_entry
) -> None:
    """Test native_value returns 'waiting_for_data' and 'disconnected' states."""
    sensor = NSServiceSensor(mock_coordinator, mock_config_entry)
    # No data
    mock_coordinator.data = None
    assert sensor.native_value == "waiting_for_data"
    # Data but no routes
    mock_coordinator.data = {"routes": {}}
    assert sensor.native_value == "no_routes"
    # Data with routes but no trips
    mock_coordinator.data = {"routes": {"r": {"trips": []}}}
    assert sensor.native_value == "disconnected"


# Fix AddEntitiesCallback mocks to accept two arguments
@pytest.mark.asyncio
async def test_async_setup_entry_no_routes_addentities(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test async_setup_entry with no routes configured adds only service sensor."""
    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = {"coordinator": mock_coordinator}
    mock_coordinator.data = {"routes": {}, "stations": []}
    entities = []

    def mock_add_entities(
        new_entities, update_before_add=False, *, config_subentry_id=None
    ):
        entities.extend(new_entities)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)
    assert len(entities) == 1
    assert isinstance(entities[0], NSServiceSensor)


@pytest.mark.asyncio
async def test_async_setup_entry_with_routes_addentities(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test async_setup_entry with routes configured adds service and trip sensors."""
    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = {"coordinator": mock_coordinator}
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
    assert len(entities) == 3
    assert isinstance(entities[0], NSServiceSensor)
    assert isinstance(entities[1], NSTripSensor)
    assert isinstance(entities[2], NSTripSensor)


@pytest.mark.asyncio
async def test_async_setup_entry_no_coordinator_data_addentities(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test async_setup_entry when coordinator has no data adds only service sensor."""
    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = {"coordinator": mock_coordinator}
    mock_coordinator.data = None
    entities = []

    def mock_add_entities(
        new_entities, update_before_add=False, *, config_subentry_id=None
    ):
        entities.extend(new_entities)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)
    assert len(entities) == 1
    assert isinstance(entities[0], NSServiceSensor)


class DummyTrip:
    """A dummy trip object for testing NSTripSensor fields and datetime formatting."""

    def __init__(
        self,
        departure_time_actual=None,
        departure_time_planned=None,
        arrival_time_actual=None,
        arrival_time_planned=None,
        departure_platform_planned=None,
        departure_platform_actual=None,
        arrival_platform_planned=None,
        arrival_platform_actual=None,
        status=None,
        nr_transfers=None,
    ) -> None:
        """Initialize a dummy trip with optional fields for testing."""
        self.departure_time_actual = departure_time_actual
        self.departure_time_planned = departure_time_planned
        self.arrival_time_actual = arrival_time_actual
        self.arrival_time_planned = arrival_time_planned
        self.departure_platform_planned = departure_platform_planned
        self.departure_platform_actual = departure_platform_actual
        self.arrival_platform_planned = arrival_platform_planned
        self.arrival_platform_actual = arrival_platform_actual
        self.status = status
        self.nr_transfers = nr_transfers


def test_trip_sensor_native_value_first_trip_actual(
    mock_coordinator, mock_config_entry
) -> None:
    """Test NSTripSensor.native_value with first_trip having departure_time_actual."""
    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"
    dt = datetime(2024, 1, 1, 8, 15)
    first_trip = DummyTrip(departure_time_actual=dt)
    mock_coordinator.data = {
        "routes": {
            route_key: {"route": route, "first_trip": first_trip, "trips": [first_trip]}
        }
    }
    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, route_key)
    assert sensor.native_value == "08:15"


def test_trip_sensor_native_value_first_trip_planned(
    mock_coordinator, mock_config_entry
) -> None:
    """Test NSTripSensor.native_value with first_trip having only departure_time_planned."""
    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"
    dt = datetime(2024, 1, 1, 9, 30)
    first_trip = DummyTrip(departure_time_actual=None, departure_time_planned=dt)
    mock_coordinator.data = {
        "routes": {
            route_key: {"route": route, "first_trip": first_trip, "trips": [first_trip]}
        }
    }
    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, route_key)
    assert sensor.native_value == "09:30"


def test_trip_sensor_native_value_first_trip_not_datetime(
    mock_coordinator, mock_config_entry
) -> None:
    """Test NSTripSensor.native_value with first_trip having non-datetime departure_time."""
    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"
    first_trip = DummyTrip(
        departure_time_actual="notadatetime", departure_time_planned=None
    )
    mock_coordinator.data = {
        "routes": {
            route_key: {"route": route, "first_trip": first_trip, "trips": [first_trip]}
        }
    }
    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, route_key)
    assert sensor.native_value == "no_time"


def test_trip_sensor_extra_state_attributes_full(
    mock_coordinator, mock_config_entry
) -> None:
    """Test NSTripSensor.extra_state_attributes with all fields in first_trip and next_trip."""
    route = {"name": "Test Route", "from": "AMS", "to": "UTR", "via": "ASS"}
    route_key = "Test Route_AMS_UTR"
    dt1 = datetime(2024, 1, 1, 8, 15)
    dt2 = datetime(2024, 1, 1, 9, 0)
    dt3 = datetime(2024, 1, 1, 10, 0)
    dt4 = datetime(2024, 1, 1, 10, 30)
    first_trip = DummyTrip(
        departure_time_actual=dt1,
        departure_time_planned=dt2,
        arrival_time_actual=dt3,
        arrival_time_planned=dt4,
        departure_platform_planned="5a",
        departure_platform_actual="6b",
        arrival_platform_planned="1",
        arrival_platform_actual="2",
        status="ON_TIME",
        nr_transfers=1,
    )
    next_trip = DummyTrip(departure_time_actual=dt4)
    mock_coordinator.data = {
        "routes": {
            route_key: {
                "route": route,
                "first_trip": first_trip,
                "next_trip": next_trip,
                "trips": [first_trip, next_trip],
            }
        }
    }
    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, route_key)
    attrs = sensor.extra_state_attributes
    assert attrs["route_from"] == "AMS"
    assert attrs["route_to"] == "UTR"
    assert attrs["route_via"] == "ASS"
    assert attrs["departure_platform_planned"] == "5a"
    assert attrs["departure_platform_actual"] == "6b"
    assert attrs["arrival_platform_planned"] == "1"
    assert attrs["arrival_platform_actual"] == "2"
    assert attrs["status"] == "ON_TIME"
    assert attrs["nr_transfers"] == 1
    assert attrs["departure_time_planned"] == "09:00"
    assert attrs["departure_time_actual"] == "08:15"
    assert attrs["arrival_time_planned"] == "10:30"
    assert attrs["arrival_time_actual"] == "10:00"
    assert attrs["next_departure"] == "10:30"


def test_trip_sensor_extra_state_attributes_partial_and_nondatetime(
    mock_coordinator, mock_config_entry
) -> None:
    """Test NSTripSensor.extra_state_attributes with missing fields and non-datetime times (should raise AttributeError)."""
    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"
    first_trip = DummyTrip(
        departure_time_actual="notadatetime",
        departure_time_planned=None,
        arrival_time_actual=None,
        arrival_time_planned="notadatetime",
        departure_platform_planned=None,
        departure_platform_actual=None,
        arrival_platform_planned=None,
        arrival_platform_actual=None,
        status=None,
        nr_transfers=None,
    )
    next_trip = DummyTrip(
        departure_time_actual=None, departure_time_planned="notadatetime"
    )
    mock_coordinator.data = {
        "routes": {
            route_key: {
                "route": route,
                "first_trip": first_trip,
                "next_trip": next_trip,
                "trips": [first_trip, next_trip],
            }
        }
    }
    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, route_key)

    with pytest.raises(AttributeError):
        _ = sensor.extra_state_attributes


def test_trip_sensor_extra_state_attributes_missing_route_fields(
    mock_coordinator, mock_config_entry
) -> None:
    """Test NSTripSensor.extra_state_attributes with missing CONF_FROM/TO/VIA fields."""
    route = {"name": "Test Route"}  # No from/to/via
    route_key = "Test Route_AMS_UTR"
    mock_coordinator.data = {
        "routes": {
            route_key: {
                "route": route,
                "first_trip": None,
                "next_trip": None,
                "trips": [],
            }
        }
    }
    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, route_key)
    attrs = sensor.extra_state_attributes
    assert attrs["route_from"] is None
    assert attrs["route_to"] is None
    assert attrs["route_via"] is None


def test_trip_sensor_extra_state_attributes_all_strftime_branches(
    mock_coordinator, mock_config_entry
) -> None:
    """Test NSTripSensor.extra_state_attributes covers all strftime branches for planned/actual/planned-only/actual-only times."""
    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"
    # Only planned for departure, only actual for arrival
    first_trip = DummyTrip(
        departure_time_actual=None,
        departure_time_planned=datetime(2024, 1, 1, 7, 0),
        arrival_time_actual=datetime(2024, 1, 1, 8, 0),
        arrival_time_planned=None,
    )
    # Only planned for next_trip
    next_trip = DummyTrip(
        departure_time_actual=None,
        departure_time_planned=datetime(2024, 1, 1, 9, 0),
    )
    mock_coordinator.data = {
        "routes": {
            route_key: {
                "route": route,
                "first_trip": first_trip,
                "next_trip": next_trip,
                "trips": [first_trip, next_trip],
            }
        }
    }
    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, route_key)
    attrs = sensor.extra_state_attributes
    assert attrs["departure_time_planned"] == "07:00"
    assert attrs["arrival_time_actual"] == "08:00"
    assert attrs["next_departure"] == "09:00"
    # The other fields should not be present
    assert "departure_time_actual" not in attrs
    assert "arrival_time_planned" not in attrs


def test_trip_sensor_extra_state_attributes_all_strftime_paths(
    mock_coordinator, mock_config_entry
) -> None:
    """Test NSTripSensor.extra_state_attributes covers all strftime branches."""
    route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
    route_key = "Test Route_AMS_UTR"
    dt_departure_planned = datetime(2024, 1, 1, 7, 0)
    dt_arrival_actual = datetime(2024, 1, 1, 8, 0)
    dt_next_departure_planned = datetime(2024, 1, 1, 9, 0)
    first_trip = DummyTrip(
        departure_time_planned=dt_departure_planned,
        arrival_time_actual=dt_arrival_actual,
    )
    next_trip = DummyTrip(departure_time_planned=dt_next_departure_planned)
    mock_coordinator.data = {
        "routes": {
            route_key: {
                "route": route,
                "first_trip": first_trip,
                "next_trip": next_trip,
                "trips": [first_trip, next_trip],
            }
        }
    }
    sensor = NSTripSensor(mock_coordinator, mock_config_entry, route, route_key)
    attrs = sensor.extra_state_attributes
    assert attrs["departure_time_planned"] == "07:00"
    assert attrs["arrival_time_actual"] == "08:00"
    assert attrs["next_departure"] == "09:00"
    # The other fields should not be present
    assert "departure_time_actual" not in attrs
    assert "arrival_time_planned" not in attrs
