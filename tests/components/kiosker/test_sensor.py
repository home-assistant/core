"""Test the Kiosker sensors."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from homeassistant.components.kiosker.sensor import parse_datetime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_sensors_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up all sensors."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
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
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        mock_screensaver = MagicMock()
        mock_screensaver.visible = True

        mock_blackout = MagicMock()
        mock_blackout.visible = True
        mock_blackout.text = "Test blackout"

        mock_api.status.return_value = mock_status
        mock_api.screensaver_get_state.return_value = mock_screensaver
        mock_api.blackout_get.return_value = mock_blackout

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
                "screensaver": mock_screensaver,
                "blackout": mock_blackout,
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    # Check that all sensor entities were created
    expected_sensors = [
        "sensor.kiosker_a98be1ce_battery_level",
        "sensor.kiosker_a98be1ce_battery_state",
        "sensor.kiosker_a98be1ce_last_interaction",
        "sensor.kiosker_a98be1ce_last_motion",
        "sensor.kiosker_a98be1ce_ambient_light",
        "sensor.kiosker_a98be1ce_last_update",
        "sensor.kiosker_a98be1ce_blackout_state",
        "sensor.kiosker_a98be1ce_screensaver_visibility",
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
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
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
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = {
                "status": mock_status,
            }
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check battery level sensor
    state = hass.states.get("sensor.kiosker_a98be1ce_battery_level")
    assert state is not None
    assert state.state == "42"
    assert state.attributes["unit_of_measurement"] == "%"
    assert state.attributes["device_class"] == "battery"
    assert state.attributes["state_class"] == "measurement"


async def test_battery_state_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test battery state sensor."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
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
        mock_status.battery_state = "discharging"
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = {
                "status": mock_status,
            }
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check battery state sensor
    state = hass.states.get("sensor.kiosker_a98be1ce_battery_state")
    assert state is not None
    assert state.state == "discharging"
    assert state.attributes["icon"] == "mdi:lightning-bolt"


async def test_last_interaction_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test last interaction sensor."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
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
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = {
                "status": mock_status,
            }
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check last interaction sensor
    state = hass.states.get("sensor.kiosker_a98be1ce_last_interaction")
    assert state is not None
    assert state.state == "2025-01-01T12:00:00+00:00"
    assert state.attributes["device_class"] == "timestamp"
    assert state.attributes["icon"] == "mdi:gesture-tap"


async def test_last_motion_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test last motion sensor."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
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
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = {
                "status": mock_status,
            }
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check last motion sensor
    state = hass.states.get("sensor.kiosker_a98be1ce_last_motion")
    assert state is not None
    assert state.state == "2025-01-01T11:55:00+00:00"
    assert state.attributes["device_class"] == "timestamp"
    assert state.attributes["icon"] == "mdi:motion-sensor"


async def test_last_update_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test last update sensor."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
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
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = {
                "status": mock_status,
            }
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check last update sensor
    state = hass.states.get("sensor.kiosker_a98be1ce_last_update")
    assert state is not None
    assert state.state == "2025-01-01T12:05:00+00:00"
    assert state.attributes["device_class"] == "timestamp"
    assert state.attributes["icon"] == "mdi:update"


async def test_ambient_light_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test ambient light sensor."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
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
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"
        mock_status.ambient_light = 2.6

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = {
                "status": mock_status,
            }
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check ambient light sensor
    state = hass.states.get("sensor.kiosker_a98be1ce_ambient_light")
    assert state is not None
    assert state.state == "2.6"
    assert state.attributes["icon"] == "mdi:brightness-6"
    assert state.attributes["state_class"] == "measurement"
    # Verify no unit of measurement (unit-less sensor)
    assert "unit_of_measurement" not in state.attributes


async def test_blackout_state_sensor_active(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test blackout state sensor when blackout is active."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
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
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        # Setup blackout data
        mock_blackout = MagicMock()
        mock_blackout.visible = True
        mock_blackout.text = "Test blackout message"
        mock_blackout.background = "#000000"
        mock_blackout.foreground = "#FFFFFF"

        mock_api.status.return_value = mock_status
        mock_api.blackout_get.return_value = mock_blackout

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
                "blackout": mock_blackout,
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = {
                "status": mock_status,
                "blackout": mock_blackout,
            }
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check blackout state sensor
    state = hass.states.get("sensor.kiosker_a98be1ce_blackout_state")
    assert state is not None
    assert state.state == "active"
    assert state.attributes["icon"] == "mdi:monitor-off"
    # Check that blackout data is in extra attributes
    assert "visible" in state.attributes
    assert "text" in state.attributes
    assert "background" in state.attributes
    assert "foreground" in state.attributes


async def test_blackout_state_sensor_inactive(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test blackout state sensor when blackout is inactive."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
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
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        mock_api.status.return_value = mock_status
        mock_api.blackout_get.return_value = None

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration with no blackout data
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
                # No blackout key
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = {
                "status": mock_status,
                # No blackout key
            }
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check blackout state sensor
    state = hass.states.get("sensor.kiosker_a98be1ce_blackout_state")
    assert state is not None
    assert state.state == "inactive"
    assert state.attributes["icon"] == "mdi:monitor-off"


async def test_screensaver_visibility_sensor_visible(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test screensaver visibility sensor when screensaver is visible."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
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
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        # Setup screensaver data
        mock_screensaver = MagicMock()
        mock_screensaver.visible = True

        mock_api.status.return_value = mock_status
        mock_api.screensaver_get_state.return_value = mock_screensaver

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
                "screensaver": mock_screensaver,
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = {
                "status": mock_status,
                "screensaver": mock_screensaver,
            }
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check screensaver visibility sensor
    state = hass.states.get("sensor.kiosker_a98be1ce_screensaver_visibility")
    assert state is not None
    assert state.state == "visible"
    assert state.attributes["icon"] == "mdi:power-sleep"


async def test_screensaver_visibility_sensor_hidden(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test screensaver visibility sensor when screensaver is hidden."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
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
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        # Setup screensaver data
        mock_screensaver = MagicMock()
        mock_screensaver.visible = False

        mock_api.status.return_value = mock_status
        mock_api.screensaver_get_state.return_value = mock_screensaver

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
                "screensaver": mock_screensaver,
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = {
                "status": mock_status,
                "screensaver": mock_screensaver,
            }
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check screensaver visibility sensor
    state = hass.states.get("sensor.kiosker_a98be1ce_screensaver_visibility")
    assert state is not None
    assert state.state == "hidden"
    assert state.attributes["icon"] == "mdi:power-sleep"


async def test_sensors_missing_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test sensors when data is missing."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
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

        # Explicitly remove attributes that should be missing
        del mock_status.battery_level
        del mock_status.battery_state
        del mock_status.last_interaction
        del mock_status.last_motion
        del mock_status.ambient_light
        del mock_status.last_update

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration with missing data
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
                # No screensaver or blackout data
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = {
                "status": mock_status,
                # No screensaver or blackout data
            }
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check that sensors handle missing data gracefully
    sensors_with_unknown_state = [
        "sensor.kiosker_a98be1ce_battery_level",
        "sensor.kiosker_a98be1ce_battery_state",
        "sensor.kiosker_a98be1ce_last_interaction",
        "sensor.kiosker_a98be1ce_last_motion",
        "sensor.kiosker_a98be1ce_ambient_light",
        "sensor.kiosker_a98be1ce_last_update",
    ]

    for sensor_id in sensors_with_unknown_state:
        state = hass.states.get(sensor_id)
        assert state is not None
        assert state.state == "unknown"

    # Blackout sensor should be "inactive" when no data
    blackout_state = hass.states.get("sensor.kiosker_a98be1ce_blackout_state")
    assert blackout_state is not None
    assert blackout_state.state == "inactive"

    # Screensaver sensor should be "hidden" when no data (this is the default)
    screensaver_state = hass.states.get(
        "sensor.kiosker_a98be1ce_screensaver_visibility"
    )
    assert screensaver_state is not None
    assert screensaver_state.state == "hidden"


async def test_sensor_unique_ids(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test sensor unique ID generation."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
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
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = mock_config_entry.runtime_data
            coordinator.data = {
                "status": mock_status,
            }
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check that sensor entities have correct unique IDs
    entity_registry = er.async_get(hass)

    expected_unique_ids = [
        ("sensor.kiosker_test_sen_battery_level", "TEST_SENSOR_ID_battery_level"),
        ("sensor.kiosker_test_sen_battery_state", "TEST_SENSOR_ID_battery_state"),
        ("sensor.kiosker_test_sen_last_interaction", "TEST_SENSOR_ID_last_interaction"),
        ("sensor.kiosker_test_sen_last_motion", "TEST_SENSOR_ID_last_motion"),
        ("sensor.kiosker_test_sen_ambient_light", "TEST_SENSOR_ID_ambient_light"),
        ("sensor.kiosker_test_sen_last_update", "TEST_SENSOR_ID_last_update"),
        ("sensor.kiosker_test_sen_blackout_state", "TEST_SENSOR_ID_blackout_state"),
        (
            "sensor.kiosker_test_sen_screensaver_visibility",
            "TEST_SENSOR_ID_screensaver_visibility",
        ),
    ]

    for entity_id, expected_unique_id in expected_unique_ids:
        entity = entity_registry.async_get(entity_id)
        assert entity is not None, f"Entity {entity_id} not found"
        assert entity.unique_id == expected_unique_id


async def test_parse_datetime_function() -> None:
    """Test the parse_datetime utility function."""

    # Test with None
    assert parse_datetime(None) is None

    # Test with datetime object
    dt = datetime(2025, 1, 1, 12, 0, 0)
    assert parse_datetime(dt) == dt

    # Test with ISO string
    result = parse_datetime("2025-01-01T12:00:00Z")
    assert result is not None
    assert result.year == 2025
    assert result.month == 1
    assert result.day == 1
    assert result.hour == 12

    # Test with invalid string
    assert parse_datetime("invalid") is None

    # Test with non-string, non-datetime
    assert parse_datetime(123) is None
