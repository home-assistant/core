"""Home Assistant integration tests for writable Inepro display settings."""

from datetime import timedelta
import struct
from unittest.mock import patch

from inepro_metering.const import MeterFamily, TransportType

from homeassistant.components.inepro_metering.const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_FAMILY,
    CONF_METERS,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOPBITS,
    CONF_TRANSPORT,
    CONF_VARIANT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


def _encode_float(value: float) -> list[int]:
    """Encode a float into two big-endian Modbus registers."""
    packed = struct.pack(">f", value)
    return list(struct.unpack(">HH", packed))


def _build_register_map(
    *,
    serial_hi: int,
    serial_lo: int,
    product_code: int,
    backlight_mode: int,
    backlight_level: int,
    backlight_timeout: int,
    legal_obis: int,
    non_legal_obis: int,
    legal_cycle: int,
    non_legal_cycle: int,
    tariff_mode: int,
    orientation: int,
) -> dict[int, int]:
    """Build a minimal fake register map that includes display settings."""
    registers: dict[int, int] = {}

    def add(address: int, words: list[int]) -> None:
        for offset, word in enumerate(words):
            registers[address + offset] = word

    add(0x4000, [serial_hi, serial_lo])
    add(0x4002, [product_code])
    add(0x4005, _encode_float(1.0))
    add(0x4007, _encode_float(1.0))
    add(0x4009, _encode_float(2.0))
    add(0x4010, [legal_cycle])
    add(0x4015, [0x0000])
    add(0x4025, [product_code])
    add(0x4032, [orientation])
    add(0x4033, [non_legal_obis])
    add(0x4171, [backlight_level])
    add(0x4C00, [legal_obis])
    add(0x4C01, [tariff_mode])
    add(0x4C02, [backlight_mode])
    add(0x4C04, [backlight_timeout])
    add(0x4C05, [non_legal_cycle])
    add(0x5000, _encode_float(230.0))
    add(0x5008, _encode_float(50.0))
    add(0x500A, _encode_float(0.5))
    add(0x5012, _encode_float(0.1))
    add(0x501A, _encode_float(0.0))
    add(0x5022, _encode_float(0.1))
    add(0x502A, _encode_float(1.0))
    add(0x6000, [0x0000, 0x0001])
    add(0x600C, [0x0000, 0x0001])
    add(0x6018, [0x0000, 0x0000])
    add(0x6030, [0x0000, 0x0000])
    add(0x603C, [0x0000, 0x0000])

    return registers


class FakeWritableModbusClient:
    """Fake Modbus client for one single-meter writable-settings entry."""

    instances: list[FakeWritableModbusClient] = []

    def __init__(self, config) -> None:
        """Initialize the fake client."""
        self._registers = _build_register_map(
            serial_hi=0x2515,
            serial_lo=0x0002,
            product_code=0x0850,
            backlight_mode=2,
            backlight_level=100,
            backlight_timeout=5,
            legal_obis=1,
            non_legal_obis=0,
            legal_cycle=5,
            non_legal_cycle=10,
            tariff_mode=0,
            orientation=0,
        )
        self.writes: list[tuple[int, int, int]] = []
        self.instances.append(self)

    async def async_read_registers(self, register_type, address, count, slave_id):
        """Return fake register values."""
        return [self._registers.get(address + offset, 0) for offset in range(count)]

    async def async_write_register(self, address, value, slave_id):
        """Record a fake single-register write."""
        self.writes.append((slave_id, address, int(value)))
        self._registers[address] = int(value)

    async def async_close(self) -> None:
        """Close the fake client."""
        return


class FakeStaleAfterWriteModbusClient(FakeWritableModbusClient):
    """Fake client that returns one stale setting poll after a successful write."""

    instances: list[FakeStaleAfterWriteModbusClient] = []

    def __init__(self, config) -> None:
        """Initialize the fake client."""
        super().__init__(config)
        self._stale_reads: dict[int, int] = {}
        self.instances.append(self)

    async def async_read_registers(self, register_type, address, count, slave_id):
        """Return fake register values."""
        if count == 1 and address in self._stale_reads:
            return [self._stale_reads.pop(address)]
        return await super().async_read_registers(
            register_type, address, count, slave_id
        )

    async def async_write_register(self, address, value, slave_id):
        """Record a fake single-register write."""
        previous = self._registers.get(address, 0)
        await super().async_write_register(address, value, slave_id)
        self._stale_reads[address] = previous


class FakeWritableSerialBusModbusClient:
    """Fake Modbus client for writable settings on a multi-meter RTU bus."""

    instances: list[FakeWritableSerialBusModbusClient] = []

    def __init__(self, config) -> None:
        """Initialize the fake client."""
        self._registers_by_slave = {
            1: _build_register_map(
                serial_hi=0x2515,
                serial_lo=0x0002,
                product_code=0x0850,
                backlight_mode=2,
                backlight_level=100,
                backlight_timeout=5,
                legal_obis=1,
                non_legal_obis=0,
                legal_cycle=5,
                non_legal_cycle=10,
                tariff_mode=0,
                orientation=0,
            ),
            157: _build_register_map(
                serial_hi=0x2526,
                serial_lo=0x0007,
                product_code=0x0801,
                backlight_mode=0,
                backlight_level=60,
                backlight_timeout=9,
                legal_obis=1,
                non_legal_obis=1,
                legal_cycle=8,
                non_legal_cycle=12,
                tariff_mode=2,
                orientation=1,
            ),
        }
        self.writes: list[tuple[int, int, int]] = []
        self.instances.append(self)

    async def async_read_registers(self, register_type, address, count, slave_id):
        """Return fake register values."""
        registers = self._registers_by_slave[slave_id]
        return [registers.get(address + offset, 0) for offset in range(count)]

    async def async_write_register(self, address, value, slave_id):
        """Record a fake single-register write."""
        self.writes.append((slave_id, address, int(value)))
        self._registers_by_slave[slave_id][address] = int(value)

    async def async_close(self) -> None:
        """Close the fake client."""
        return


async def test_single_meter_display_settings_entities_expose_current_values(
    hass,
) -> None:
    """Display settings should be shown through switches, selects, and sliders."""
    FakeWritableModbusClient.instances.clear()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Meter",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_850",
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
        FakeWritableModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.get("select.test_meter_backlight_mode").state == "Button Activated"
    )
    assert hass.states.get("select.test_meter_backlight_level").state == "100%"
    assert (
        hass.states.get("select.test_meter_display_tariff_mode").state
        == "Automatic (Show Used Tariffs)"
    )
    assert hass.states.get("select.test_meter_lcd_orientation").state == "Standard"
    assert hass.states.get("switch.test_meter_legal_lcd_obis_codes").state == "on"
    assert hass.states.get("switch.test_meter_non_legal_lcd_obis_codes").state == "off"
    assert float(hass.states.get("number.test_meter_backlight_timeout").state) == 5.0
    assert float(hass.states.get("number.test_meter_legal_lcd_cycle_time").state) == 5.0
    assert (
        float(hass.states.get("number.test_meter_non_legal_lcd_cycle_time").state)
        == 10.0
    )


async def test_single_meter_display_settings_write_registers_and_refresh(
    hass,
) -> None:
    """Writes through HA setting entities should update the underlying registers."""
    FakeWritableModbusClient.instances.clear()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Meter",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_850",
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
        FakeWritableModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "select",
            "select_option",
            {
                "entity_id": "select.test_meter_backlight_mode",
                "option": "Always Off",
            },
            blocking=True,
        )
        await hass.services.async_call(
            "number",
            "set_value",
            {
                "entity_id": "number.test_meter_backlight_timeout",
                "value": 12,
            },
            blocking=True,
        )
        await hass.services.async_call(
            "switch",
            "turn_on",
            {
                "entity_id": "switch.test_meter_non_legal_lcd_obis_codes",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

    client = FakeWritableModbusClient.instances[0]
    assert client.writes == [
        (1, 0x4C02, 1),
        (1, 0x4C04, 12),
        (1, 0x4033, 1),
    ]
    assert hass.states.get("select.test_meter_backlight_mode").state == "Always Off"
    assert float(hass.states.get("number.test_meter_backlight_timeout").state) == 12.0
    assert hass.states.get("switch.test_meter_non_legal_lcd_obis_codes").state == "on"


async def test_single_meter_setting_write_ignores_one_stale_follow_up_poll(
    hass,
) -> None:
    """A stale poll immediately after a verified write should not revert the UI value."""
    FakeStaleAfterWriteModbusClient.instances.clear()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Meter",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_850",
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
        FakeStaleAfterWriteModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "select",
            "select_option",
            {
                "entity_id": "select.test_meter_backlight_level",
                "option": "20%",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        coordinator = entry.runtime_data
        coordinator._suppress_refresh_until = dt_util.utcnow() - timedelta(seconds=1)
        await coordinator.async_request_refresh()
        await hass.async_block_till_done()

    assert hass.states.get("select.test_meter_backlight_level").state == "20%"


async def test_serial_bus_display_setting_write_targets_correct_slave(
    hass,
) -> None:
    """Bus setting writes should go to the addressed RTU slave."""
    FakeWritableSerialBusModbusClient.instances.clear()
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
                    "name": "085125250008",
                    CONF_VARIANT: "grow_850",
                    CONF_SLAVE_ID: 1,
                    "serial_number": "085125250008",
                    "product_code": "0851",
                },
                {
                    "name": "080125260007",
                    CONF_VARIANT: "grow_800",
                    CONF_SLAVE_ID: 157,
                    "serial_number": "080125260007",
                    "product_code": "0801",
                },
            ],
        },
        version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.inepro_metering.coordinator.IneproModbusClient",
        FakeWritableSerialBusModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get("select.080125260007_backlight_level").state == "60%"
        await hass.services.async_call(
            "select",
            "select_option",
            {
                "entity_id": "select.080125260007_backlight_level",
                "option": "20%",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

    client = FakeWritableSerialBusModbusClient.instances[0]
    assert client.writes == [(157, 0x4171, 20)]
    assert hass.states.get("select.080125260007_backlight_level").state == "20%"
