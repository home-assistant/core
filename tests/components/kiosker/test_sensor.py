"""Test the Kiosker sensors."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from homeassistant.components.kiosker.coordinator import KioskerData
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_sensors_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up all sensors."""
    with patch(
        "homeassistant.components.kiosker.coordinator.KioskerAPI"
    ) as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"
        mock_status.battery_level = 85
        mock_status.battery_state = "charging"
        mock_status.last_interaction = datetime.fromisoformat(
            "2025-01-01T12:00:00+00:00"
        )
        mock_status.last_motion = datetime.fromisoformat("2025-01-01T11:55:00+00:00")

        mock_screensaver = MagicMock()
        mock_screensaver.visible = True

        mock_blackout = MagicMock()
        mock_blackout.visible = True
        mock_blackout.text = "Test blackout"
        # Mock dataclass fields for extra attributes
        mock_blackout.__dataclass_fields__ = {
            "visible": None,
            "text": None,
        }

        mock_api.status.return_value = mock_status
        mock_api.screensaver_get_state.return_value = mock_screensaver
        mock_api.blackout_get.return_value = mock_blackout

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = KioskerData(
                status=mock_status,
                screensaver=mock_screensaver,
                blackout=mock_blackout,
            )

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    # Check that all sensor entities were created
    expected_sensors = [
        "sensor.kiosker_a98be1ce_battery",
        "sensor.kiosker_a98be1ce_last_interaction",
        "sensor.kiosker_a98be1ce_last_motion",
        "sensor.kiosker_a98be1ce_ambient_light",
    ]

    for sensor_id in expected_sensors:
        state = hass.states.get(sensor_id)
        assert state is not None, f"Sensor {sensor_id} was not created"

    # Check entity registry
    entity_registry = er.async_get(hass)
    for sensor_id in expected_sensors:
        entity = entity_registry.async_get(sensor_id)
        assert entity is not None, f"Sensor {sensor_id} not in entity registry"


async def test_battery_level_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test battery level sensor."""
    with patch(
        "homeassistant.components.kiosker.coordinator.KioskerAPI"
    ) as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"
        mock_status.battery_level = 42
        mock_status.battery_state = "charging"
        mock_status.last_interaction = datetime.fromisoformat(
            "2025-01-01T12:00:00+00:00"
        )
        mock_status.last_motion = datetime.fromisoformat("2025-01-01T11:55:00+00:00")

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check battery level sensor
    state = hass.states.get("sensor.kiosker_a98be1ce_battery")
    assert state is not None
    assert state.state == "42"
    assert state.attributes["unit_of_measurement"] == "%"
    assert state.attributes["device_class"] == "battery"
    assert state.attributes["state_class"] == "measurement"


async def test_last_interaction_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test last interaction sensor."""
    with patch(
        "homeassistant.components.kiosker.coordinator.KioskerAPI"
    ) as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"
        mock_status.battery_level = 85
        mock_status.battery_state = "charging"
        mock_status.last_interaction = datetime.fromisoformat(
            "2026-03-03T22:41:09+00:00"
        )
        mock_status.last_motion = datetime.fromisoformat("2025-03-03T22:40:09+00:00")

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check last interaction sensor
    state = hass.states.get("sensor.kiosker_a98be1ce_last_interaction")
    assert state is not None
    assert state.state == "2026-03-03T22:41:09+00:00"
    assert state.attributes["device_class"] == "timestamp"


async def test_last_motion_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test last motion sensor."""
    with patch(
        "homeassistant.components.kiosker.coordinator.KioskerAPI"
    ) as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"
        mock_status.battery_level = 85
        mock_status.battery_state = "charging"
        mock_status.last_interaction = datetime.fromisoformat(
            "2025-01-01T12:00:00+00:00"
        )
        mock_status.last_motion = datetime.fromisoformat("2025-01-01T11:55:00+00:00")

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check last motion sensor
    state = hass.states.get("sensor.kiosker_a98be1ce_last_motion")
    assert state is not None
    assert state.state == "2025-01-01T11:55:00+00:00"
    assert state.attributes["device_class"] == "timestamp"


async def test_ambient_light_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test ambient light sensor."""
    with patch(
        "homeassistant.components.kiosker.coordinator.KioskerAPI"
    ) as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"
        mock_status.battery_level = 85
        mock_status.battery_state = "charging"
        mock_status.last_interaction = datetime.fromisoformat(
            "2025-01-01T12:00:00+00:00"
        )
        mock_status.last_motion = datetime.fromisoformat("2025-01-01T11:55:00+00:00")
        mock_status.ambient_light = 2.6

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check ambient light sensor
    state = hass.states.get("sensor.kiosker_a98be1ce_ambient_light")
    assert state is not None
    assert state.state == "2.6"
    assert state.attributes["state_class"] == "measurement"
    # Verify no unit of measurement (unit-less sensor)
    assert "unit_of_measurement" not in state.attributes


async def test_sensors_missing_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test sensors when data is missing."""
    with patch(
        "homeassistant.components.kiosker.coordinator.KioskerAPI"
    ) as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data with missing attributes
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration with missing data (None coordinator data)
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Test missing data by setting coordinator data to None
            coordinator = mock_config_entry.runtime_data
            coordinator.data = None
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check that sensors are unavailable when coordinator data is missing
    sensors_with_unavailable_state = [
        "sensor.kiosker_a98be1ce_battery",
        "sensor.kiosker_a98be1ce_last_interaction",
        "sensor.kiosker_a98be1ce_last_motion",
        "sensor.kiosker_a98be1ce_ambient_light",
    ]

    for sensor_id in sensors_with_unavailable_state:
        state = hass.states.get(sensor_id)
        assert state is not None
        assert state.state == "unavailable"


async def test_sensor_unique_ids(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test sensor unique ID generation."""
    with patch(
        "homeassistant.components.kiosker.coordinator.KioskerAPI"
    ) as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data with custom device ID
        mock_status = MagicMock()
        mock_status.device_id = "TEST_SENSOR_ID"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"
        mock_status.battery_level = 85
        mock_status.battery_state = "charging"
        mock_status.last_interaction = datetime.fromisoformat(
            "2025-01-01T12:00:00+00:00"
        )
        mock_status.last_motion = datetime.fromisoformat("2025-01-01T11:55:00+00:00")

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check that sensor entities have correct unique IDs
    entity_registry = er.async_get(hass)

    expected_unique_ids = [
        ("sensor.kiosker_test_sen_battery", "TEST_SENSOR_ID_batteryLevel"),
        ("sensor.kiosker_test_sen_last_interaction", "TEST_SENSOR_ID_lastInteraction"),
        ("sensor.kiosker_test_sen_last_motion", "TEST_SENSOR_ID_lastMotion"),
        ("sensor.kiosker_test_sen_ambient_light", "TEST_SENSOR_ID_ambientLight"),
    ]

    for entity_id, expected_unique_id in expected_unique_ids:
        entity = entity_registry.async_get(entity_id)
        assert entity is not None, f"Entity {entity_id} not found"
        assert entity.unique_id == expected_unique_id
