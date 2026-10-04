"""Tests for the SMA Modbus integration."""

from typing import Any

from modbus_connection.mock import MockModbusConnection, MockModbusUnit
from sma_modbus import DEVICE_CLASSES, DeviceType, DiscoveryInfo, Vendor
from sma_modbus.testing import set_input_registers

from homeassistant.components.sma_modbus.const import (
    CONF_DEVICE_TYPE,
    DEFAULT_PORT,
    DOMAIN,
)

from tests.common import MockConfigEntry

SERIAL = 30001234
UNIQUE_ID = f"SMA{SERIAL}"
HOST = "192.168.178.1"

# Registers needed for Type Label discovery (registers 30001-30056):
# The _combine_u32 helper reads (words[0] << 16) | words[1], so we split
# each 32-bit value into two 16-bit words: (value >> 16) and (value & 0xFFFF).
_REG_DISCOVERY = {
    30001: 0,  # profile_rev high
    30002: 1140,  # profile_rev low
    30003: 0,  # susy_id high
    30004: 270,  # susy_id low
    30005: 457,  # serial high (30001234 >> 16)
    30006: 51282,  # serial low (30001234 & 0xFFFF)
    30051: 0,  # device_class high (8009 >> 16)
    30052: 8009,  # device_class low
    30053: 0,  # device_model high (19085 >> 16)
    30054: 19085,  # device_model low
    30055: 0,  # vendor high (461 >> 16)
    30056: 461,  # vendor low
}


def mock_discovery_info(
    device_type: DeviceType = DeviceType.SUNNY_BOY_SMART_ENERGY,
    unit_id: int = 3,
) -> DiscoveryInfo:
    """Return a fake DiscoveryInfo."""
    return DiscoveryInfo(
        device_type=device_type,
        serial_number=SERIAL,
        unit_id=unit_id,
        susy_id=270,
        modbus_profile_revision=1140,
        device_class=8009,
        device_model=19085,
        vendor=Vendor.SMA.value,
    )


def make_mock_unit() -> MockModbusUnit:
    """Create a MockModbusUnit seeded with discovery register values."""
    connection = MockModbusConnection()
    unit = connection.for_unit(3)
    unit.input.update(_REG_DISCOVERY)
    return unit


def make_seeded_connection(device_type: DeviceType) -> MockModbusConnection:
    """Create a mock connection seeded with discovery + type-label values."""
    connection = MockModbusConnection()
    device = DEVICE_CLASSES[device_type](connection)
    set_input_registers(
        connection,
        device,
        {
            "serial_number": SERIAL,
            "device_class": mock_discovery_info(device_type).device_class,
            "device_type": mock_discovery_info(device_type).device_model,
            "vendor": Vendor.SMA.value,
        },
    )
    return connection


def make_config_entry(
    device_type: DeviceType = DeviceType.SUNNY_BOY_SMART_ENERGY,
    extra_data: dict[str, Any] | None = None,
) -> MockConfigEntry:
    """Create a config entry for the given device type."""
    data: dict[str, Any] = {
        "host": HOST,
        "port": DEFAULT_PORT,
        CONF_DEVICE_TYPE: device_type.value,
    }
    if extra_data:
        data.update(extra_data)
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data=data,
    )
