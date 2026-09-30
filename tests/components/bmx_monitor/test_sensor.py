"""Test BM2 sensor conversion, registration and entity properties."""

from unittest.mock import MagicMock, patch

import pytest
from sensor_state_data import DeviceKey, SensorUpdate

from homeassistant.components import bmx_monitor as integration
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothEntityKey,
)
from homeassistant.components.bmx_monitor import sensor
from homeassistant.components.bmx_monitor.const import DOMAIN
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH

from tests.common import MockConfigEntry

ADDRESS = "AA:BB:CC:DD:EE:FF"


@pytest.mark.parametrize("key", list(sensor.SENSOR_DESCRIPTIONS))
def test_update_conversion(key: str) -> None:
    """Map each supported reading to its HA description and entity key."""
    device_key = DeviceKey(key, ADDRESS)
    bluetooth_key = PassiveBluetoothEntityKey(key, ADDRESS)
    update = MagicMock(spec=SensorUpdate)
    device_info = MagicMock()
    update.devices = {ADDRESS: device_info}
    update.entity_descriptions = {device_key: MagicMock()}
    update.entity_values = {device_key: MagicMock(native_value=42)}
    converted_info = {"name": "BM2"}
    with patch.object(
        sensor, "sensor_device_info_to_hass_device_info", return_value=converted_info
    ) as convert:
        result = sensor.sensor_update_to_bluetooth_data_update(update)
    convert.assert_called_once_with(device_info)
    assert result.devices == {ADDRESS: converted_info}
    assert result.entity_descriptions == {
        bluetooth_key: sensor.SENSOR_DESCRIPTIONS[key]
    }
    assert result.entity_data == {bluetooth_key: 42}
    assert result.entity_names == {}


def test_empty_update() -> None:
    """An update with no readings creates no phantom entities."""
    update = MagicMock(spec=SensorUpdate)
    update.devices = {}
    update.entity_descriptions = {}
    update.entity_values = {}
    result = sensor.sensor_update_to_bluetooth_data_update(update)
    assert result.devices == {}
    assert result.entity_descriptions == {}
    assert result.entity_data == {}


@pytest.mark.usefixtures("mock_bluetooth")
async def test_platform_registration(hass: HomeAssistant) -> None:
    """Load the real sensor platform through config-entry setup."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS)
    entry.add_to_hass(hass)
    with (
        patch.object(integration, "async_address_present", return_value=True),
        patch.object(integration, "async_last_service_info", return_value=MagicMock()),
        patch.object(
            integration, "async_validate_device", return_value="valid_passive"
        ),
        patch.object(integration, "ActiveBluetoothProcessorCoordinator") as coordinator,
        patch.object(sensor, "PassiveBluetoothDataProcessor") as factory,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        factory.assert_called_once_with(sensor.sensor_update_to_bluetooth_data_update)
        processor = factory.return_value
        processor.async_add_entities_listener.assert_called_once()
        listener_args = processor.async_add_entities_listener.call_args.args
        assert listener_args[0] is sensor.BMxBluetoothSensorEntity
        assert callable(listener_args[1])
        coordinator.return_value.async_register_processor.assert_called_once_with(
            processor, SensorEntityDescription
        )
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        processor.async_add_entities_listener.return_value.assert_called_once()
        coordinator.return_value.async_register_processor.return_value.assert_called_once()


@pytest.mark.parametrize("value", [12.5, 67, "charging", None])
def test_native_value(value: float | str | None) -> None:
    """The entity exposes its processor's latest value, including missing data."""
    entity = MagicMock()
    entity.entity_key = PassiveBluetoothEntityKey("battery_voltage", ADDRESS)
    entity.processor.entity_data = {entity.entity_key: value}
    assert sensor.BMxBluetoothSensorEntity.native_value.fget(entity) == value


@pytest.mark.parametrize("available", [True, False])
def test_availability(available: bool) -> None:
    """Unavailable processors expose assumed rather than live sensor states."""
    entity = MagicMock()
    entity.processor.available = available
    assert sensor.BMxBluetoothSensorEntity.available.fget(entity) is available
    assert sensor.BMxBluetoothSensorEntity.assumed_state.fget(entity) is not available


def test_device_identity() -> None:
    """Every sensor belongs to the same Bluetooth monitor device."""
    entity = MagicMock()
    entity.processor.coordinator.address = ADDRESS
    info = sensor.BMxBluetoothSensorEntity.device_info.fget(entity)
    assert info["identifiers"] == {(DOMAIN, ADDRESS)}
    assert info["connections"] == {(CONNECTION_BLUETOOTH, ADDRESS)}
    assert info["name"] == "BM2 battery monitor"
    assert info["manufacturer"] == "Shenzhen Leagend Optoelectronics"
