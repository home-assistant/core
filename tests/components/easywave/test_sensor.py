"""Tests for the sensor platform of the Easywave Core integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.easywave import EasywaveRuntimeData
from homeassistant.components.easywave.const import (
    DOMAIN,
    EVENT_GATEWAY_CONNECTED,
    EVENT_GATEWAY_DISCONNECTED,
    EVENT_GATEWAY_STATUS_CHANGED,
)
from homeassistant.components.easywave.sensor import (
    EasywaveGatewaySensor,
    async_setup_entry,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from tests.common import MockConfigEntry


@pytest.fixture
def gateway_sensor(
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
) -> EasywaveGatewaySensor:
    """Return a gateway sensor instance with a mocked coordinator."""
    return EasywaveGatewaySensor(mock_config_entry, mock_coordinator)


async def test_sensor_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
) -> None:
    """Test sensor platform setup from runtime_data."""
    mock_config_entry.runtime_data = EasywaveRuntimeData(
        coordinator=mock_coordinator,
        frequency="868 MHz",
        country="DE",
    )
    async_add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert async_add_entities.called
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert isinstance(entities[0], EasywaveGatewaySensor)
    assert entities[0].coordinator is mock_coordinator


def test_sensor_class_attributes(gateway_sensor: EasywaveGatewaySensor) -> None:
    """Test sensor class attributes."""
    assert gateway_sensor._attr_has_entity_name is True
    assert gateway_sensor._attr_translation_key == "gateway_status"
    assert gateway_sensor._attr_device_class == SensorDeviceClass.ENUM
    assert gateway_sensor._attr_entity_category == EntityCategory.DIAGNOSTIC
    assert "connected" in gateway_sensor._attr_options
    assert "disconnected" in gateway_sensor._attr_options


def test_sensor_unique_id(
    gateway_sensor: EasywaveGatewaySensor,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor unique ID format."""
    assert (
        gateway_sensor._attr_unique_id == f"{mock_config_entry.entry_id}_rx11_gateway"
    )


def test_sensor_initial_state(gateway_sensor: EasywaveGatewaySensor) -> None:
    """Test sensor initial state is disconnected/None."""
    assert gateway_sensor._last_status == "disconnected"
    assert gateway_sensor._current_status is None


def test_native_value_before_started(gateway_sensor: EasywaveGatewaySensor) -> None:
    """Test native_value is None before HA started (recorder sees transition)."""
    assert gateway_sensor.native_value is None


def test_native_value_after_update(gateway_sensor: EasywaveGatewaySensor) -> None:
    """Test native_value returns current status after set."""
    gateway_sensor._current_status = "connected"
    assert gateway_sensor.native_value == "connected"


def test_icon_connected(gateway_sensor: EasywaveGatewaySensor) -> None:
    """Test icon when connected."""
    gateway_sensor._current_status = "connected"
    assert gateway_sensor.icon == "mdi:usb"


def test_icon_disconnected(gateway_sensor: EasywaveGatewaySensor) -> None:
    """Test icon when disconnected."""
    gateway_sensor._current_status = "disconnected"
    assert gateway_sensor.icon == "mdi:close-thick"


def test_icon_none(gateway_sensor: EasywaveGatewaySensor) -> None:
    """Test icon when status is None."""
    gateway_sensor._current_status = None
    assert gateway_sensor.icon == "mdi:close-thick"


def test_available_always_true(gateway_sensor: EasywaveGatewaySensor) -> None:
    """Test sensor availability is always True."""
    assert gateway_sensor.available is True


def test_extra_state_attributes(gateway_sensor: EasywaveGatewaySensor) -> None:
    """Test extra state attributes contain expected keys."""
    attrs = gateway_sensor.extra_state_attributes
    assert "device_path" in attrs
    assert "connected" in attrs


def test_extra_state_attributes_with_details(
    gateway_sensor: EasywaveGatewaySensor,
) -> None:
    """Test extra state attributes include version info when available."""
    # The mock_coordinator fixture provides versions
    attrs = gateway_sensor.extra_state_attributes
    assert "usb_serial_number" in attrs
    assert "hardware_version" in attrs
    assert "firmware_version" in attrs


def test_device_info(gateway_sensor: EasywaveGatewaySensor) -> None:
    """Test device_info from USB device registry."""
    info = gateway_sensor.device_info
    assert info is not None
    assert info["name"] == "RX11 USB Transceiver"
    assert info["manufacturer"] == "ELDAT"


def test_device_info_serial_number(gateway_sensor: EasywaveGatewaySensor) -> None:
    """Test device_info includes serial number."""
    info = gateway_sensor.device_info
    assert info["serial_number"] == "12345"


def test_device_info_fallback_unknown_device(
    mock_coordinator: MagicMock,
) -> None:
    """Test device_info falls back to entry data for unknown VID/PID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "device_path": "/dev/ttyACM0",
            "usb_vid": 0x9999,
            "usb_pid": 0x9999,
            "usb_serial_number": "12345",
            "usb_manufacturer": "ELDAT",
            "usb_product": "RX11 USB Transceiver",
        },
    )
    sensor = EasywaveGatewaySensor(entry, mock_coordinator)
    info = sensor.device_info
    assert info["manufacturer"] == "ELDAT"


def test_connection_status_connected(gateway_sensor: EasywaveGatewaySensor) -> None:
    """Test _connection_status returns connected when transceiver is connected."""
    assert gateway_sensor._connection_status() == "connected"


def test_connection_status_disconnected_offline(
    gateway_sensor: EasywaveGatewaySensor,
) -> None:
    """Test _connection_status returns disconnected when offline."""
    gateway_sensor.coordinator.is_offline = True
    assert gateway_sensor._connection_status() == "disconnected"


def test_handle_coordinator_update(
    hass: HomeAssistant,
    gateway_sensor: EasywaveGatewaySensor,
) -> None:
    """Test _handle_coordinator_update updates current_status."""
    gateway_sensor.hass = hass
    gateway_sensor.async_write_ha_state = MagicMock()
    gateway_sensor._ha_started = True

    gateway_sensor._handle_coordinator_update()

    assert gateway_sensor._current_status == "connected"
    assert gateway_sensor.async_write_ha_state.called


async def test_handle_coordinator_update_fires_connected_event(
    hass: HomeAssistant,
    gateway_sensor: EasywaveGatewaySensor,
) -> None:
    """Test that transitioning to connected fires EVENT_GATEWAY_CONNECTED."""
    gateway_sensor.hass = hass
    gateway_sensor.async_write_ha_state = MagicMock()
    gateway_sensor._ha_started = True
    gateway_sensor._last_status = "disconnected"

    events: list[str] = []
    hass.bus.async_listen(
        EVENT_GATEWAY_CONNECTED, lambda e: events.append(e.event_type)
    )
    hass.bus.async_listen(
        EVENT_GATEWAY_STATUS_CHANGED, lambda e: events.append(e.event_type)
    )

    gateway_sensor._handle_coordinator_update()
    await hass.async_block_till_done()

    assert EVENT_GATEWAY_STATUS_CHANGED in events
    assert EVENT_GATEWAY_CONNECTED in events


async def test_handle_coordinator_update_fires_disconnected_event(
    hass: HomeAssistant,
    gateway_sensor: EasywaveGatewaySensor,
) -> None:
    """Test that transitioning to disconnected fires EVENT_GATEWAY_DISCONNECTED."""
    gateway_sensor.hass = hass
    gateway_sensor.async_write_ha_state = MagicMock()
    gateway_sensor._ha_started = True
    gateway_sensor._last_status = "connected"
    gateway_sensor.coordinator.is_offline = True
    gateway_sensor.coordinator.transceiver.is_connected = False

    events: list[str] = []
    hass.bus.async_listen(
        EVENT_GATEWAY_DISCONNECTED, lambda e: events.append(e.event_type)
    )
    hass.bus.async_listen(
        EVENT_GATEWAY_STATUS_CHANGED, lambda e: events.append(e.event_type)
    )

    gateway_sensor._handle_coordinator_update()
    await hass.async_block_till_done()

    assert EVENT_GATEWAY_STATUS_CHANGED in events
    assert EVENT_GATEWAY_DISCONNECTED in events


# ── _connection_status edge cases ───────────────────────────────────────────


def test_connection_status_transceiver_not_connected(
    gateway_sensor: EasywaveGatewaySensor,
) -> None:
    """Test _connection_status falls through to disconnected when transceiver not connected."""
    gateway_sensor.coordinator.is_offline = False
    gateway_sensor.coordinator.transceiver.is_connected = False
    assert gateway_sensor._connection_status() == "disconnected"


def test_connection_status_transceiver_none(
    gateway_sensor: EasywaveGatewaySensor,
) -> None:
    """Test _connection_status when transceiver is None."""
    gateway_sensor.coordinator.is_offline = False
    gateway_sensor.coordinator.transceiver = None
    assert gateway_sensor._connection_status() == "disconnected"


# ── _update_gateway_device_info ─────────────────────────────────────────────


def test_update_device_info_no_transceiver(
    hass: HomeAssistant,
    gateway_sensor: EasywaveGatewaySensor,
) -> None:
    """Test _update_gateway_device_info returns early without transceiver."""
    gateway_sensor.hass = hass
    gateway_sensor.coordinator.transceiver = None
    # Should not raise
    gateway_sensor._update_gateway_device_info()


def test_update_device_info_no_change(
    hass: HomeAssistant,
    gateway_sensor: EasywaveGatewaySensor,
) -> None:
    """Test _update_gateway_device_info does nothing when values match."""
    gateway_sensor.hass = hass
    gateway_sensor.async_write_ha_state = MagicMock()
    # Values already match the mock (serial=12345, hw=1.0, fw=2.0)
    gateway_sensor._update_gateway_device_info()
    gateway_sensor.async_write_ha_state.assert_not_called()


def test_update_device_info_serial_change(
    hass: HomeAssistant,
    gateway_sensor: EasywaveGatewaySensor,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _update_gateway_device_info updates serial number."""
    mock_config_entry.add_to_hass(hass)
    gateway_sensor.hass = hass
    gateway_sensor.async_write_ha_state = MagicMock()
    gateway_sensor.coordinator.transceiver.usb_serial_number = "NEW_SERIAL"

    with patch("homeassistant.components.easywave.sensor.dr.async_get") as mock_dr:
        mock_registry = MagicMock()
        mock_dr.return_value = mock_registry

        gateway_sensor._update_gateway_device_info()

    assert gateway_sensor._usb_serial_number == "NEW_SERIAL"
    mock_registry.async_get_or_create.assert_called_once()
    gateway_sensor.async_write_ha_state.assert_called_once()


def test_update_device_info_hw_version_change(
    hass: HomeAssistant,
    gateway_sensor: EasywaveGatewaySensor,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _update_gateway_device_info updates hardware version."""
    mock_config_entry.add_to_hass(hass)
    gateway_sensor.hass = hass
    gateway_sensor.async_write_ha_state = MagicMock()
    gateway_sensor.coordinator.transceiver.hw_version = "3.5"

    with patch("homeassistant.components.easywave.sensor.dr.async_get") as mock_dr:
        mock_dr.return_value = MagicMock()
        gateway_sensor._update_gateway_device_info()

    assert gateway_sensor._hw_version == "3.5"


def test_update_device_info_fw_version_change(
    hass: HomeAssistant,
    gateway_sensor: EasywaveGatewaySensor,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _update_gateway_device_info updates firmware version."""
    mock_config_entry.add_to_hass(hass)
    gateway_sensor.hass = hass
    gateway_sensor.async_write_ha_state = MagicMock()
    gateway_sensor.coordinator.transceiver.fw_version = "4.2"

    with patch("homeassistant.components.easywave.sensor.dr.async_get") as mock_dr:
        mock_dr.return_value = MagicMock()
        gateway_sensor._update_gateway_device_info()

    assert gateway_sensor._sw_version == "4.2"


# ── async_added_to_hass ────────────────────────────────────────────────────


async def test_async_added_to_hass_running(
    hass: HomeAssistant,
    gateway_sensor: EasywaveGatewaySensor,
) -> None:
    """Test async_added_to_hass when HA is already running."""
    gateway_sensor.hass = hass
    gateway_sensor.async_write_ha_state = MagicMock()
    gateway_sensor.async_on_remove = MagicMock()

    await gateway_sensor.async_added_to_hass()
    await hass.async_block_till_done()

    # _handle_coordinator_update should have been called via loop.call_soon
    assert gateway_sensor._current_status is not None
    # Should have registered listeners
    assert gateway_sensor.async_on_remove.call_count >= 1


async def test_async_added_to_hass_not_started(
    hass: HomeAssistant,
    gateway_sensor: EasywaveGatewaySensor,
) -> None:
    """Test async_added_to_hass when HA has not started yet."""
    gateway_sensor.hass = hass
    gateway_sensor.async_write_ha_state = MagicMock()
    gateway_sensor.async_on_remove = MagicMock()

    # Simulate HA not yet fully running (still in starting phase)
    hass.set_state(CoreState.starting)
    await gateway_sensor.async_added_to_hass()

    # _current_status should still be None (waiting for STARTED event)
    assert gateway_sensor._current_status is None

    # Now fire the start event
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    # Now the handler should have run
    assert gateway_sensor._current_status is not None
