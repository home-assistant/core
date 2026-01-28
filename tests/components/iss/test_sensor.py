"""Test ISS sensor."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.iss.const import DOMAIN
from homeassistant.components.iss.coordinator.people import IssPeopleCoordinator
from homeassistant.components.iss.coordinator.position import IssPositionCoordinator
from homeassistant.components.iss.sensor import (
    IssPeopleSensor,
    IssPositionSensor,
    async_setup_entry,
)
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_position_coordinator(hass: HomeAssistant) -> IssPositionCoordinator:
    """Return a mock position coordinator."""
    coordinator = MagicMock(spec=IssPositionCoordinator)
    coordinator.data = {
        "latitude": "51.5074",
        "longitude": "-0.1278",
    }
    coordinator.last_update_success = True
    coordinator.async_add_listener = MagicMock()
    return coordinator


@pytest.fixture
def mock_people_coordinator(hass: HomeAssistant) -> IssPeopleCoordinator:
    """Return a mock people coordinator."""
    coordinator = MagicMock(spec=IssPeopleCoordinator)
    coordinator.data = {"number": 7, "people": []}
    coordinator.async_add_listener = MagicMock()
    return coordinator


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={},
        entry_id="test_entry_id",
        options={CONF_SHOW_ON_MAP: False},
    )


class TestIssPositionSensor:
    """Tests for IssPositionSensor class."""

    def test_sensor_initialization(
        self,
        mock_position_coordinator: IssPositionCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test sensor initialization."""
        sensor = IssPositionSensor(
            position_coordinator=mock_position_coordinator,
            entry=mock_config_entry,
            show=False,
        )

        assert sensor._attr_unique_id == "test_entry_id_location"
        assert sensor._attr_icon == "mdi:space-station"
        assert sensor._attr_has_entity_name is True
        assert sensor._attr_translation_key == "location"
        assert sensor._show_on_map is False

    def test_sensor_initialization_show_on_map(
        self,
        mock_position_coordinator: IssPositionCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test sensor initialization with show_on_map enabled."""
        sensor = IssPositionSensor(
            position_coordinator=mock_position_coordinator,
            entry=mock_config_entry,
            show=True,
        )

        assert sensor._show_on_map is True

    def test_sensor_device_info(
        self,
        mock_position_coordinator: IssPositionCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test sensor device info."""
        sensor = IssPositionSensor(
            position_coordinator=mock_position_coordinator,
            entry=mock_config_entry,
            show=False,
        )

        device_info = sensor._attr_device_info
        assert device_info is not None
        assert device_info["identifiers"] == {(DOMAIN, "test_entry_id")}
        assert device_info["name"] == "ISS"

    def test_native_value_with_data(
        self,
        mock_position_coordinator: IssPositionCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test native_value property with position data."""
        sensor = IssPositionSensor(
            position_coordinator=mock_position_coordinator,
            entry=mock_config_entry,
            show=False,
        )

        value = sensor.native_value
        assert value == "Latitude:  51.507°\nLongitude: -0.128°"

    def test_native_value_with_precise_coordinates(
        self,
        mock_position_coordinator: IssPositionCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test native_value with precise coordinates."""
        mock_position_coordinator.data = {
            "latitude": "51.507456789",
            "longitude": "-0.127823456",
        }

        sensor = IssPositionSensor(
            position_coordinator=mock_position_coordinator,
            entry=mock_config_entry,
            show=False,
        )

        value = sensor.native_value
        # Should be rounded to 3 decimal places
        assert value == "Latitude:  51.507°\nLongitude: -0.128°"

    def test_native_value_without_data(
        self,
        mock_position_coordinator: IssPositionCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test native_value property without position data."""
        mock_position_coordinator.data = None

        sensor = IssPositionSensor(
            position_coordinator=mock_position_coordinator,
            entry=mock_config_entry,
            show=False,
        )

        assert sensor.native_value is None

    def test_extra_state_attributes_show_on_map_false(
        self,
        mock_position_coordinator: IssPositionCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test extra_state_attributes when show_on_map is False."""
        sensor = IssPositionSensor(
            position_coordinator=mock_position_coordinator,
            entry=mock_config_entry,
            show=False,
        )

        attrs = sensor.extra_state_attributes

        assert "lat" in attrs
        assert "long" in attrs
        assert attrs["lat"] == "51.5074"
        assert attrs["long"] == "-0.1278"
        assert attrs["last_updated"] is True
        assert ATTR_LATITUDE not in attrs
        assert ATTR_LONGITUDE not in attrs
        assert "entity_picture" not in attrs
        assert "friendly_name" not in attrs

    def test_extra_state_attributes_show_on_map_true(
        self,
        mock_position_coordinator: IssPositionCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test extra_state_attributes when show_on_map is True."""
        sensor = IssPositionSensor(
            position_coordinator=mock_position_coordinator,
            entry=mock_config_entry,
            show=True,
        )

        attrs = sensor.extra_state_attributes

        assert ATTR_LATITUDE in attrs
        assert ATTR_LONGITUDE in attrs
        assert attrs[ATTR_LATITUDE] == 51.51  # Rounded to 2 decimal places
        assert attrs[ATTR_LONGITUDE] == -0.13
        assert (
            attrs["entity_picture"]
            == "https://brands.home-assistant.io/iss/icon@2x.png"
        )
        assert attrs["friendly_name"] == "ISS"
        assert attrs["last_updated"] is True
        assert "lat" not in attrs
        assert "long" not in attrs

    def test_extra_state_attributes_without_data(
        self,
        mock_position_coordinator: IssPositionCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test extra_state_attributes without position data."""
        mock_position_coordinator.data = None

        sensor = IssPositionSensor(
            position_coordinator=mock_position_coordinator,
            entry=mock_config_entry,
            show=False,
        )

        attrs = sensor.extra_state_attributes
        assert attrs == {}

    def test_extra_state_attributes_with_edge_coordinates(
        self,
        mock_position_coordinator: IssPositionCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test extra_state_attributes with edge case coordinates."""
        mock_position_coordinator.data = {
            "latitude": "0.0",
            "longitude": "0.0",
        }

        sensor = IssPositionSensor(
            position_coordinator=mock_position_coordinator,
            entry=mock_config_entry,
            show=True,
        )

        attrs = sensor.extra_state_attributes
        assert attrs[ATTR_LATITUDE] == 0.0
        assert attrs[ATTR_LONGITUDE] == 0.0


class TestIssPeopleSensor:
    """Tests for IssPeopleSensor class."""

    def test_sensor_initialization(
        self,
        mock_people_coordinator: IssPeopleCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test people sensor initialization."""
        sensor = IssPeopleSensor(
            people_coordinator=mock_people_coordinator,
            entry=mock_config_entry,
        )

        assert sensor._attr_unique_id == "test_entry_id_people"
        assert sensor._attr_icon == "mdi:account-multiple"
        assert sensor._attr_has_entity_name is True
        assert sensor._attr_translation_key == "people_on_board"
        assert sensor._attr_native_unit_of_measurement == "people"

    def test_sensor_device_info(
        self,
        mock_people_coordinator: IssPeopleCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test people sensor device info."""
        sensor = IssPeopleSensor(
            people_coordinator=mock_people_coordinator,
            entry=mock_config_entry,
        )

        device_info = sensor._attr_device_info
        assert device_info is not None
        assert device_info["identifiers"] == {(DOMAIN, "test_entry_id")}
        assert device_info["name"] == "ISS"

    def test_native_value_with_data(
        self,
        mock_people_coordinator: IssPeopleCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test native_value property with people data."""
        mock_people_coordinator.data = {"number": 7, "people": []}

        sensor = IssPeopleSensor(
            people_coordinator=mock_people_coordinator,
            entry=mock_config_entry,
        )

        assert sensor.native_value == 7

    def test_native_value_without_data(
        self,
        mock_people_coordinator: IssPeopleCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test native_value property without people data."""
        mock_people_coordinator.data = None

        sensor = IssPeopleSensor(
            people_coordinator=mock_people_coordinator,
            entry=mock_config_entry,
        )

        assert sensor.native_value is None

    def test_extra_state_attributes_with_people(
        self,
        mock_people_coordinator: IssPeopleCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test extra_state_attributes with people list."""
        mock_people_coordinator.data = {
            "number": 3,
            "people": [
                {"name": "Alice", "craft": "ISS"},
                {"name": "Bob", "craft": "ISS"},
                {"name": "Charlie", "craft": "Tiangong"},
            ],
        }

        sensor = IssPeopleSensor(
            people_coordinator=mock_people_coordinator,
            entry=mock_config_entry,
        )

        attrs = sensor.extra_state_attributes
        assert "people" in attrs
        assert attrs["people"] == ["Alice", "Bob", "Charlie"]

    def test_extra_state_attributes_without_data(
        self,
        mock_people_coordinator: IssPeopleCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test extra_state_attributes without people data."""
        mock_people_coordinator.data = None

        sensor = IssPeopleSensor(
            people_coordinator=mock_people_coordinator,
            entry=mock_config_entry,
        )

        attrs = sensor.extra_state_attributes
        assert attrs == {}

    def test_extra_state_attributes_empty_people_list(
        self,
        mock_people_coordinator: IssPeopleCoordinator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test extra_state_attributes with empty people list."""
        mock_people_coordinator.data = {"number": 0, "people": []}

        sensor = IssPeopleSensor(
            people_coordinator=mock_people_coordinator,
            entry=mock_config_entry,
        )

        attrs = sensor.extra_state_attributes
        assert "people" in attrs
        assert attrs["people"] == []


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_position_coordinator: IssPositionCoordinator,
    mock_people_coordinator: IssPeopleCoordinator,
) -> None:
    """Test async_setup_entry."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        entry_id="test_entry_id",
        options={CONF_SHOW_ON_MAP: True},
    )

    # Mock hass.data
    hass.data[DOMAIN] = {
        "test_entry_id": {
            "position_coordinator": mock_position_coordinator,
            "people_coordinator": mock_people_coordinator,
        }
    }

    entities_added = []

    def mock_async_add_entities(entities):
        entities_added.extend(entities)

    await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

    assert len(entities_added) == 2
    assert isinstance(entities_added[0], IssPositionSensor)
    assert isinstance(entities_added[1], IssPeopleSensor)
    assert entities_added[0]._show_on_map is True


async def test_async_setup_entry_show_on_map_default(
    hass: HomeAssistant,
    mock_position_coordinator: IssPositionCoordinator,
    mock_people_coordinator: IssPeopleCoordinator,
) -> None:
    """Test async_setup_entry with default show_on_map value."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        entry_id="test_entry_id",
        options={},  # No CONF_SHOW_ON_MAP specified
    )

    # Mock hass.data
    hass.data[DOMAIN] = {
        "test_entry_id": {
            "position_coordinator": mock_position_coordinator,
            "people_coordinator": mock_people_coordinator,
        }
    }

    entities_added = []

    def mock_async_add_entities(entities):
        entities_added.extend(entities)

    await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

    assert len(entities_added) == 2
    # Default should be False for position sensor
    assert entities_added[0]._show_on_map is False
