# mypy: ignore-errors
"""Test Grandstream sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.grandstream_home.const import DOMAIN
from homeassistant.components.grandstream_home.sensor import (
    DEVICE_SENSORS,
    GrandstreamDeviceSensor,
    GrandstreamSensorEntityDescription,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_sensor_setup(
    hass: HomeAssistant,
) -> None:
    """Test sensor setup."""
    # Create mock config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_entry_id",
        data={"host": "192.168.1.100", "name": "Test Device"},
    )
    config_entry.add_to_hass(hass)

    # Create mock coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"phone_status": "idle"}
    mock_coordinator.last_update_success = True

    # Create mock device info
    mock_device_info = MagicMock()

    # Create mock API
    mock_api = MagicMock()
    mock_api.is_ha_control_enabled = True
    mock_api.is_online = True
    mock_api.is_account_locked = False
    mock_api.is_authenticated = True

    # Setup runtime_data
    mock_runtime_data = MagicMock()
    mock_runtime_data.coordinator = mock_coordinator
    mock_runtime_data.device_info = mock_device_info
    mock_runtime_data.unique_id = "test_unique_id"
    mock_runtime_data.api = mock_api
    config_entry.runtime_data = mock_runtime_data

    # Track added entities
    added_entities = []

    def mock_async_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, config_entry, mock_async_add_entities)

    # Should create device sensors
    assert len(added_entities) == 1
    assert isinstance(added_entities[0], GrandstreamDeviceSensor)


def test_device_sensor_native_value() -> None:
    """Test device sensor native_value."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"phone_status": "idle"}
    mock_coordinator.last_update_success = True

    # Create mock config entry with runtime_data
    mock_api = MagicMock()
    mock_api.is_ha_control_enabled = True
    mock_api.is_online = True
    mock_api.is_account_locked = False
    mock_api.is_authenticated = True

    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api

    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = mock_runtime_data
    mock_coordinator.config_entry = mock_config_entry

    device_info = MagicMock()
    description = DEVICE_SENSORS[0]  # phone_status

    sensor = GrandstreamDeviceSensor(
        mock_coordinator, device_info, "test_unique_id", description
    )

    assert sensor.native_value == "idle"


def test_device_sensor_ha_control_disabled() -> None:
    """Test device sensor returns ha_control_disabled."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"phone_status": "idle"}
    mock_coordinator.last_update_success = True

    mock_api = MagicMock()
    mock_api.is_ha_control_enabled = False
    mock_api.is_online = True
    mock_api.is_account_locked = False
    mock_api.is_authenticated = True

    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api

    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = mock_runtime_data
    mock_coordinator.config_entry = mock_config_entry

    device_info = MagicMock()
    description = DEVICE_SENSORS[0]

    sensor = GrandstreamDeviceSensor(
        mock_coordinator, device_info, "test_unique_id", description
    )

    assert sensor.native_value == "ha_control_disabled"


def test_device_sensor_offline() -> None:
    """Test device sensor returns offline."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"phone_status": "idle"}
    mock_coordinator.last_update_success = True

    mock_api = MagicMock()
    mock_api.is_ha_control_enabled = True
    mock_api.is_online = False
    mock_api.is_account_locked = False
    mock_api.is_authenticated = True

    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api

    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = mock_runtime_data
    mock_coordinator.config_entry = mock_config_entry

    device_info = MagicMock()
    description = DEVICE_SENSORS[0]

    sensor = GrandstreamDeviceSensor(
        mock_coordinator, device_info, "test_unique_id", description
    )

    assert sensor.native_value == "offline"


def test_device_sensor_account_locked() -> None:
    """Test device sensor returns account_locked."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"phone_status": "idle"}
    mock_coordinator.last_update_success = True

    mock_api = MagicMock()
    mock_api.is_ha_control_enabled = True
    mock_api.is_online = True
    mock_api.is_account_locked = True
    mock_api.is_authenticated = True

    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api

    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = mock_runtime_data
    mock_coordinator.config_entry = mock_config_entry

    device_info = MagicMock()
    description = DEVICE_SENSORS[0]

    sensor = GrandstreamDeviceSensor(
        mock_coordinator, device_info, "test_unique_id", description
    )

    assert sensor.native_value == "account_locked"


def test_device_sensor_auth_failed() -> None:
    """Test device sensor returns auth_failed."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"phone_status": "idle"}
    mock_coordinator.last_update_success = True

    mock_api = MagicMock()
    mock_api.is_ha_control_enabled = True
    mock_api.is_online = True
    mock_api.is_account_locked = False
    mock_api.is_authenticated = False

    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api

    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = mock_runtime_data
    mock_coordinator.config_entry = mock_config_entry

    device_info = MagicMock()
    description = DEVICE_SENSORS[0]

    sensor = GrandstreamDeviceSensor(
        mock_coordinator, device_info, "test_unique_id", description
    )

    assert sensor.native_value == "auth_failed"


def test_sensor_availability() -> None:
    """Test sensor availability."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"phone_status": "idle"}

    device_info = MagicMock()
    description = DEVICE_SENSORS[0]

    sensor = GrandstreamDeviceSensor(
        mock_coordinator, device_info, "test_unique_id", description
    )

    # Available when coordinator is available
    mock_coordinator.last_update_success = True
    assert sensor.available is True

    # Unavailable when coordinator fails
    mock_coordinator.last_update_success = False
    assert sensor.available is False


def test_sensor_unique_id() -> None:
    """Test sensor unique ID."""
    mock_coordinator = MagicMock()
    device_info = MagicMock()
    description = DEVICE_SENSORS[0]

    sensor = GrandstreamDeviceSensor(
        mock_coordinator, device_info, "test_unique_id", description
    )

    assert sensor.unique_id == "test_unique_id_phone_status"


def test_sensor_native_value_no_key_path() -> None:
    """Test sensor native_value returns None when no key_path."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"phone_status": "idle"}
    mock_coordinator.config_entry = None  # No config entry

    device_info = MagicMock()

    # Create a description without key_path
    description = GrandstreamSensorEntityDescription(
        key="test_sensor",
        # No key_path set
    )

    sensor = GrandstreamDeviceSensor(
        mock_coordinator, device_info, "test_unique_id", description
    )

    # Should return None when no key_path
    assert sensor.native_value is None


def test_sensor_handle_coordinator_update() -> None:
    """Test sensor handles coordinator update."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"phone_status": "idle"}
    device_info = MagicMock()
    description = DEVICE_SENSORS[0]

    sensor = GrandstreamDeviceSensor(
        mock_coordinator, device_info, "test_unique_id", description
    )

    # Test that _handle_coordinator_update calls async_write_ha_state
    with patch.object(sensor, "async_write_ha_state") as mock_write:
        sensor._handle_coordinator_update()
        mock_write.assert_called_once()
