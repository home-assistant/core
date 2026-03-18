"""Tests for the sensor platform of the Easywave Core integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, STATE_UNKNOWN
from homeassistant.components.sensor import SensorDeviceClass

from homeassistant.components.easywave.const import (
    CONF_DEVICE_PATH,
    CONF_USB_MANUFACTURER,
    CONF_USB_PID,
    CONF_USB_PRODUCT,
    CONF_USB_SERIAL_NUMBER,
    CONF_USB_VID,
    DOMAIN,
    EVENT_GATEWAY_CONNECTED,
    EVENT_GATEWAY_DISCONNECTED,
    EVENT_GATEWAY_STATUS_CHANGED,
)
from homeassistant.components.easywave.sensor import (
    EasywaveGatewaySensor,
    async_setup_entry,
)


@pytest.fixture
def gateway_sensor(mock_config_entry) -> EasywaveGatewaySensor:
    """Return a gateway sensor instance."""
    return EasywaveGatewaySensor(mock_config_entry)


@pytest.mark.asyncio
async def test_sensor_setup_entry(hass: HomeAssistant, mock_config_entry):
    """Test sensor platform setup."""
    async_add_entities = AsyncMock()
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    assert async_add_entities.called
    args, _kwargs = async_add_entities.call_args
    entities = args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], EasywaveGatewaySensor)


def test_sensor_attributes(gateway_sensor: EasywaveGatewaySensor):
    """Test sensor attributes."""
    assert gateway_sensor._attr_has_entity_name is True
    assert gateway_sensor._attr_translation_key == "gateway_status"
    assert gateway_sensor._attr_device_class == SensorDeviceClass.ENUM
    assert "connected" in gateway_sensor._attr_options
    assert "disconnected" in gateway_sensor._attr_options


def test_sensor_unique_id(gateway_sensor: EasywaveGatewaySensor, mock_config_entry):
    """Test sensor unique ID."""
    expected_id = f"{mock_config_entry.entry_id}_rx11_gateway"
    assert gateway_sensor._attr_unique_id == expected_id


def test_sensor_initial_status(gateway_sensor: EasywaveGatewaySensor):
    """Test sensor initial status."""
    assert gateway_sensor._last_status == "disconnected"
    assert gateway_sensor._current_status is None


def test_sensor_native_value_before_started(gateway_sensor: EasywaveGatewaySensor):
    """Test native_value before HA started."""
    # Before started, should return None to show unknown in logbook
    assert gateway_sensor.native_value is None


def test_sensor_native_value_after_started(gateway_sensor: EasywaveGatewaySensor):
    """Test native_value after initialization."""
    gateway_sensor._current_status = "connected"
    assert gateway_sensor.native_value == "connected"


def test_sensor_icon_connected(gateway_sensor: EasywaveGatewaySensor):
    """Test icon when connected."""
    gateway_sensor._current_status = "connected"
    assert gateway_sensor.icon == "mdi:usb"


def test_sensor_icon_connecting(gateway_sensor: EasywaveGatewaySensor):
    """Test icon when connecting."""
    gateway_sensor._current_status = "connecting"
    assert gateway_sensor.icon == "mdi:usb-flash-drive"


def test_sensor_icon_hardware_error(gateway_sensor: EasywaveGatewaySensor):
    """Test icon for hardware error."""
    gateway_sensor._current_status = "hardware_error"
    assert gateway_sensor.icon == "mdi:usb-port"


def test_sensor_icon_error(gateway_sensor: EasywaveGatewaySensor):
    """Test icon for error state."""
    gateway_sensor._current_status = "error"
    assert gateway_sensor.icon == "mdi:alert-circle"


def test_sensor_icon_disconnected(gateway_sensor: EasywaveGatewaySensor):
    """Test icon when disconnected."""
    gateway_sensor._current_status = "disconnected"
    assert gateway_sensor.icon == "mdi:close-thick"


def test_sensor_icon_none(gateway_sensor: EasywaveGatewaySensor):
    """Test icon when status is None."""
    gateway_sensor._current_status = None
    assert gateway_sensor.icon == "mdi:close-thick"


def test_sensor_available(gateway_sensor: EasywaveGatewaySensor):
    """Test sensor availability."""
    assert gateway_sensor.available is True


def test_sensor_extra_state_attributes(gateway_sensor: EasywaveGatewaySensor):
    """Test extra state attributes."""
    attributes = gateway_sensor.extra_state_attributes
    
    assert "device_path" in attributes
    assert "usb_serial_number" in attributes
    assert "hardware_version" in attributes
    assert "firmware_version" in attributes
    assert "connected" in attributes


def test_sensor_device_info_from_registry(gateway_sensor: EasywaveGatewaySensor):
    """Test device_info loads from USB_DEVICE_NAMES."""
    device_info = gateway_sensor.device_info
    
    assert device_info is not None
    assert device_info.name == "RX11 USB Transceiver"
    assert device_info.manufacturer == "ELDAT"
    assert "12345" in str(device_info.serial_number)


def test_sensor_device_info_fallback(mock_config_entry, mock_hass):
    """Test device_info fallback to entry data when not in registry."""
    mock_config_entry.data[CONF_USB_VID] = 0x9999
    mock_config_entry.data[CONF_USB_PID] = 0x9999
    sensor = EasywaveGatewaySensor(mock_config_entry)
    
    device_info = sensor.device_info
    
    # Should fall back to usb_product/usb_manufacturer from entry
    assert device_info.manufacturer == "ELDAT"


def test_get_connection_status_key_stub(gateway_sensor: EasywaveGatewaySensor):
    """Test _get_connection_status_key stub implementation."""
    # In CORE, stub always returns "connected"
    assert gateway_sensor._get_connection_status_key() == "connected"


def test_is_connected_stub(gateway_sensor: EasywaveGatewaySensor):
    """Test _is_connected stub implementation."""
    # In CORE, stub always returns True
    assert gateway_sensor._is_connected() is True


@pytest.mark.asyncio
async def test_handle_status_update(gateway_sensor: EasywaveGatewaySensor, hass: HomeAssistant):
    """Test _handle_status_update method."""
    gateway_sensor.hass = hass
    gateway_sensor.async_write_ha_state = AsyncMock()
    
    gateway_sensor._handle_status_update()
    
    assert gateway_sensor._current_status == "connected"
    assert gateway_sensor.async_write_ha_state.called


@pytest.mark.asyncio
async def test_status_change_fires_events(gateway_sensor: EasywaveGatewaySensor, hass: HomeAssistant):
    """Test that status changes fire gateway events."""
    gateway_sensor.hass = hass
    gateway_sensor.async_write_ha_state = AsyncMock()
    
    # Mock the bus fire method
    hass.bus.async_fire = MagicMock()
    
    gateway_sensor._handle_status_update()
    
    # EVENT_GATEWAY_CONNECTED should be fired
    assert hass.bus.async_fire.called


@pytest.mark.asyncio
async def test_async_update(gateway_sensor: EasywaveGatewaySensor, hass: HomeAssistant):
    """Test async_update method."""
    gateway_sensor.hass = hass
    gateway_sensor.async_write_ha_state = AsyncMock()
    
    await gateway_sensor.async_update()
    
    assert gateway_sensor._current_status is not None
