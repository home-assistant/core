"""Home Assistant switch-platform tests for Inepro Metering."""

from unittest.mock import patch

from inepro_metering.commands import WIFI_ENABLE_ADDRESS
from inepro_metering.const import MeterFamily, TransportType

from homeassistant.components.inepro_metering.const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_FAMILY,
    CONF_METERS,
    CONF_PARITY,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOPBITS,
    CONF_TIMEOUT,
    CONF_TRANSPORT,
    CONF_VARIANT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


class RecordingSwitchModbusClient:
    """Stateful fake Modbus client for writable switch tests."""

    writes: list[tuple[int, tuple[int, ...], int, bool]] = []

    def __init__(self, config) -> None:
        """Initialize the fake client."""
        self._registers_by_slave = {
            1: {WIFI_ENABLE_ADDRESS: 1},
            157: {WIFI_ENABLE_ADDRESS: 1},
        }

    async def async_read_registers(self, register_type, address, count, slave_id):
        """Return fake register values."""
        del register_type
        registers = self._registers_by_slave[slave_id]
        return [registers.get(address + offset, 0) for offset in range(count)]

    async def async_write_register(self, address, value, slave_id):
        """Record a fake single-register write."""
        self.writes.append((address, (value,), slave_id, False))
        self._registers_by_slave[slave_id][address] = value

    async def async_write_registers(self, address, values, slave_id):
        """Record a fake multiple-register write."""
        normalized_values = tuple(values)
        self.writes.append((address, normalized_values, slave_id, True))
        for offset, value in enumerate(normalized_values):
            self._registers_by_slave[slave_id][address + offset] = value

    async def async_close(self) -> None:
        """Close the fake client."""
        return


def _switch_entity_id(hass, entry_id: str) -> str:
    """Resolve the switch entity ID from the preserved unique ID pattern."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "switch",
        DOMAIN,
        f"{entry_id}_wifi_support_switch",
    )
    assert entity_id is not None
    return entity_id


async def test_single_meter_wifi_switch_uses_shared_write_setting_model(
    hass,
) -> None:
    """The HA switch wrapper should delegate write behavior to the shared setting model."""
    RecordingSwitchModbusClient.writes = []
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Write Meter",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.SERIAL.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            CONF_SERIAL_PORT: "COM7",
            CONF_BAUDRATE: 9600,
            CONF_BYTESIZE: 8,
            CONF_PARITY: "E",
            CONF_STOPBITS: 1,
            CONF_TIMEOUT: 3,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.inepro_metering.coordinator.IneproModbusClient",
        RecordingSwitchModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = _switch_entity_id(hass, entry.entry_id)
        assert hass.states.get(entity_id).state == "on"

        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert RecordingSwitchModbusClient.writes == [(WIFI_ENABLE_ADDRESS, (0,), 1, False)]
    assert hass.states.get(_switch_entity_id(hass, entry.entry_id)).state == "off"


async def test_serial_bus_wifi_switch_writes_to_selected_slave(
    hass,
) -> None:
    """A serial-bus switch should keep HA thin and target the shared library write route."""
    RecordingSwitchModbusClient.writes = []
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Inepro Serial Bus COM5",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_TRANSPORT: TransportType.SERIAL.value,
            CONF_SCAN_INTERVAL: 15,
            CONF_SERIAL_PORT: "COM5",
            CONF_BAUDRATE: 9600,
            CONF_BYTESIZE: 8,
            CONF_PARITY: "E",
            CONF_STOPBITS: 1,
            CONF_TIMEOUT: 3,
            CONF_METERS: [
                {
                    "name": "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SLAVE_ID: 157,
                    "serial_number": "075625480002",
                    "product_code": "0756",
                }
            ],
        },
        version=3,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.inepro_metering.coordinator.IneproModbusClient",
        RecordingSwitchModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = _switch_entity_id(hass, entry.entry_id)
        assert hass.states.get(entity_id).state == "on"

        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert RecordingSwitchModbusClient.writes == [
        (WIFI_ENABLE_ADDRESS, (0,), 157, False)
    ]
    assert hass.states.get(_switch_entity_id(hass, entry.entry_id)).state == "off"
