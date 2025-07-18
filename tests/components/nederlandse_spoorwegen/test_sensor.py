"""Test the Nederlandse Spoorwegen sensor logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.nederlandse_spoorwegen import DOMAIN, NSRuntimeData
from homeassistant.components.nederlandse_spoorwegen.coordinator import (
    NSDataUpdateCoordinator,
)
from homeassistant.components.nederlandse_spoorwegen.sensor import async_setup_entry
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
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.NSAPIWrapper"
    ) as mock_api_wrapper_class:
        # Mock stations with required station codes
        mock_station_asd = type(
            "Station", (), {"code": "ASD", "name": "Amsterdam Centraal"}
        )()
        mock_station_rtd = type(
            "Station", (), {"code": "RTD", "name": "Rotterdam Centraal"}
        )()

        # Set up the mock API wrapper
        mock_api_wrapper = AsyncMock()
        mock_api_wrapper.get_stations.return_value = [
            mock_station_asd,
            mock_station_rtd,
        ]
        mock_api_wrapper.get_trips.return_value = []
        mock_api_wrapper.validate_api_key.return_value = None
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
