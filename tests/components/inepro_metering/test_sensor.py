"""Home Assistant integration setup tests for Inepro Metering sensors."""

import struct
from unittest.mock import patch

from inepro_metering.const import MeterFamily, TransportType
from inepro_metering.modbus import (
    IneproDeviceIdentification,
    IneproReadError,
    IneproTcpGatewayInfo,
)
from inepro_metering.wifi import (
    WIFI_APPLY_ADDRESS,
    WIFI_ENABLE_ADDRESS,
    WIFI_PASSWORD_ADDRESS,
    WIFI_SSID_ADDRESS,
)
import pytest

from homeassistant.components.inepro_metering import (
    EXC_WIFI_CREDENTIALS_INVALID,
    EXC_WIFI_CREDENTIALS_METER_NOT_FOUND,
    EXC_WIFI_CREDENTIALS_UNSUPPORTED,
)
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
from homeassistant.components.inepro_metering.coordinator import (
    IneproMeteringCoordinator,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


def _encode_float(value: float) -> list[int]:
    """Encode a float into two big-endian Modbus registers."""
    packed = struct.pack(">f", value)
    return list(struct.unpack(">HH", packed))


def _encode_uint32(value: int) -> list[int]:
    """Encode a uint32 into two big-endian Modbus registers."""
    packed = struct.pack(">I", value)
    return list(struct.unpack(">HH", packed))


def _encode_int32(value: int) -> list[int]:
    """Encode an int32 into two big-endian Modbus registers."""
    packed = struct.pack(">i", value)
    return list(struct.unpack(">HH", packed))


def _register_map() -> dict[int, int]:
    """Build a fake register map for the GROW 850 profile."""
    registers: dict[int, int] = {}

    def add(address: int, words: list[int]) -> None:
        for offset, word in enumerate(words):
            registers[address + offset] = word

    add(0x4000, [0x2515, 0x0002])
    add(0x4002, [0x0850])
    add(0x4005, _encode_float(1.0))
    add(0x4007, _encode_float(1.0))
    add(0x4009, _encode_float(2.0))
    add(0x4015, [0x0000])
    add(0x401B, _encode_uint32(0x6A479857))
    add(0x401D, _encode_uint32(0x00000001))
    add(0x4023, _encode_uint32(0x6A479857))
    add(0x4025, [0x0850])
    add(0x5000, _encode_float(230.5))
    add(0x5008, _encode_float(50.0))
    add(0x500A, _encode_float(15.25))
    add(0x5012, _encode_float(3.2))
    add(0x501A, _encode_float(0.4))
    add(0x5022, _encode_float(3.5))
    add(0x502A, _encode_float(0.91))
    add(0x503A, _encode_float(0.2))
    add(0x503C, _encode_float(24.5))
    add(0x6000, _encode_int32(9845))
    add(0x600C, _encode_uint32(12345))
    add(0x6018, _encode_uint32(2500))
    add(0x6030, _encode_uint32(4800))
    add(0x603C, _encode_uint32(300))

    return registers


def _register_map_unknown_crc() -> dict[int, int]:
    """Build a fake register map with CRCs that are not yet mapped to builds."""
    registers = _register_map()
    registers[0x401B] = 0xB478
    registers[0x401C] = 0xFEE9
    registers[0x4023] = 0xB999
    registers[0x4024] = 0xF660
    return registers


def _register_map_faulted() -> dict[int, int]:
    """Build a fake register map with multiple active GROW fault bits."""
    registers = _register_map()
    registers[0x4015] = 0x00C4
    return registers


def _register_map_grow_750() -> dict[int, int]:
    """Build a fake register map for the GROW 750 profile."""
    registers: dict[int, int] = {}

    def add(address: int, words: list[int]) -> None:
        for offset, word in enumerate(words):
            registers[address + offset] = word

    add(0x4000, [0x2548, 0x0002])
    add(0x4002, [0x0756])
    add(0x4005, _encode_float(1.0))
    add(0x4007, _encode_float(1.0))
    add(0x4009, _encode_float(2.03))
    add(0x4015, [0x0000])
    add(0x401B, _encode_uint32(0xB478FEE9))
    add(0x401D, _encode_uint32(0x00000001))
    add(0x4023, _encode_uint32(0xB999F660))
    add(0x4025, [0x0756])
    add(0x4C06, [0x0001])
    add(0x4C07, [0x0001])
    add(0x4C64, [0x0001])
    add(0x5000, _encode_float(236.9))
    add(0x5002, _encode_float(236.7))
    add(0x5004, _encode_float(237.1))
    add(0x5006, _encode_float(236.8))
    add(0x5008, _encode_float(50.06))
    add(0x500A, _encode_float(0.0))
    add(0x500C, _encode_float(0.0))
    add(0x500E, _encode_float(0.0))
    add(0x5010, _encode_float(0.0))
    add(0x5012, _encode_float(0.0))
    add(0x5014, _encode_float(0.0))
    add(0x5016, _encode_float(0.0))
    add(0x5018, _encode_float(0.0))
    add(0x501A, _encode_float(0.0))
    add(0x501C, _encode_float(0.0))
    add(0x501E, _encode_float(0.0))
    add(0x5020, _encode_float(0.0))
    add(0x5022, _encode_float(0.0))
    add(0x5024, _encode_float(0.0))
    add(0x5026, _encode_float(0.0))
    add(0x5028, _encode_float(0.0))
    add(0x502A, _encode_float(1.0))
    add(0x502C, _encode_float(1.0))
    add(0x502E, _encode_float(1.0))
    add(0x5030, _encode_float(1.0))
    add(0x5032, _encode_float(410.1))
    add(0x5034, _encode_float(409.9))
    add(0x5036, _encode_float(410.3))
    add(0x5038, _encode_float(410.1))
    add(0x503A, _encode_float(0.0))
    add(0x503C, _encode_float(22.0))
    add(0x503E, _encode_float(1.5))
    add(0x5040, _encode_float(1.6))
    add(0x5042, _encode_float(1.4))
    add(0x5044, _encode_float(0.0))
    add(0x5046, _encode_float(0.0))
    add(0x5048, _encode_float(0.0))
    add(0x504A, _encode_float(1.5))
    add(0x504C, _encode_float(0.0))
    add(0x6000, _encode_int32(91))
    add(0x600C, _encode_uint32(91))
    add(0x6018, _encode_uint32(0))
    add(0x6030, _encode_uint32(0))
    add(0x603C, _encode_uint32(0))
    add(0x1010, _encode_int32(0))
    add(0x1012, _encode_int32(0))
    add(0x1100, [0x0000])

    return registers


def _register_map_pro_380() -> dict[int, int]:
    """Build a fake register map for the PRO380 profile."""
    registers: dict[int, int] = {}

    def add(address: int, words: list[int]) -> None:
        for offset, word in enumerate(words):
            registers[address + offset] = word

    add(0x4000, [0x1234, 0x5678])
    add(0x4002, [0x0380])
    add(0x4003, [0x0001])
    add(0x4004, [0x2580])
    add(0x4005, _encode_float(2.18))
    add(0x4007, _encode_float(2.18))
    add(0x4009, _encode_float(1.02))
    add(0x400B, [0x0063])
    add(0x400D, _encode_float(1000.0))
    add(0x4011, [0x0001])
    add(0x4015, [0x0000])
    add(0x4016, [0x0003])
    add(0x4017, [0x0001])
    add(0x401B, _encode_uint32(0x89ABCDEF))
    add(0x401D, _encode_uint32(0x00000001))
    add(0x5002, _encode_float(230.1))
    add(0x5004, _encode_float(231.2))
    add(0x5006, _encode_float(229.8))
    add(0x5008, _encode_float(50.01))
    add(0x500C, _encode_float(10.0))
    add(0x500E, _encode_float(9.8))
    add(0x5010, _encode_float(10.2))
    add(0x5012, _encode_float(6.789))
    add(0x5014, _encode_float(2.123))
    add(0x5016, _encode_float(2.234))
    add(0x5018, _encode_float(2.432))
    add(0x501A, _encode_float(1.234))
    add(0x501C, _encode_float(0.411))
    add(0x501E, _encode_float(0.402))
    add(0x5020, _encode_float(0.421))
    add(0x5022, _encode_float(7.123))
    add(0x5024, _encode_float(2.322))
    add(0x5026, _encode_float(2.401))
    add(0x5028, _encode_float(2.400))
    add(0x502A, _encode_float(0.952))
    add(0x502C, _encode_float(0.954))
    add(0x502E, _encode_float(0.951))
    add(0x5030, _encode_float(0.949))
    add(0x6000, _encode_float(1234.567))
    add(0x600C, _encode_float(1200.125))
    add(0x6018, _encode_float(34.442))
    add(0x6024, _encode_float(456.789))
    add(0x6030, _encode_float(400.111))
    add(0x603C, _encode_float(56.678))

    return registers


class FakeModbusClient:
    """Very small fake Modbus client for coordinator setup tests."""

    def __init__(self, config) -> None:
        """Initialize the fake client."""
        self._registers = _register_map()

    async def async_read_registers(self, register_type, address, count, slave_id):
        """Return fake register values."""
        return [self._registers.get(address + offset, 0) for offset in range(count)]

    async def async_read_device_identification(self, slave_id):
        """Return fake device identification."""
        return IneproDeviceIdentification(
            manufacturer_name="inepro Metering B.V.",
            product_name="879-3120",
            version="V1.0.2744",
        )

    async def async_close(self) -> None:
        """Close the fake client."""
        return


class FakeModbusClientUnknownCrc(FakeModbusClient):
    """Fake Modbus client that returns raw unknown CRC values."""

    def __init__(self, config) -> None:
        """Initialize the fake client."""
        self._registers = _register_map_unknown_crc()


class FakeModbusClientFault(FakeModbusClient):
    """Fake Modbus client that returns an active GROW error bitfield."""

    def __init__(self, config) -> None:
        """Initialize the fake client."""
        self._registers = _register_map_faulted()


class FakeGatewayModbusClient(FakeModbusClient):
    """Fake Modbus client for one single meter behind a TCP gateway."""

    async def async_read_tcp_gateway_info(self):
        """Return fake TCP gateway information."""
        return IneproTcpGatewayInfo(
            device_type_code=330,
            device_type="TCP Gateway",
            hardware_version="1",
            serial_number="033023260122",
            firmware_type=5,
            firmware_version="1.0.973",
            bootloader_version="1.0.845",
        )


class FakeProModbusClient:
    """Fake Modbus client for PRO profile setup tests."""

    def __init__(self, config) -> None:
        """Initialize the fake client."""
        self._registers = _register_map_pro_380()

    async def async_read_registers(self, register_type, address, count, slave_id):
        """Return fake register values."""
        return [self._registers.get(address + offset, 0) for offset in range(count)]

    async def async_read_device_identification(self, slave_id):
        """Return fake device identification."""
        return IneproDeviceIdentification(
            manufacturer_name="inepro Metering B.V.",
            product_name="PRO380",
            version="V2.18",
        )

    async def async_close(self) -> None:
        """Close the fake client."""
        return


class FakeSerialBusModbusClient:
    """Fake Modbus client that returns different maps per RTU slave."""

    def __init__(self, config) -> None:
        """Initialize the fake client."""
        self._registers_by_slave = {
            1: _register_map(),
            157: _register_map_grow_750(),
        }
        self._device_info_by_slave = {
            1: IneproDeviceIdentification(
                manufacturer_name="inepro Metering B.V.",
                product_name="879-3121",
                version="V1.0.2536",
            ),
            157: IneproDeviceIdentification(
                manufacturer_name="inepro Metering B.V.",
                product_name="879-3120",
                version="V1.0.2744",
            ),
        }

    async def async_read_registers(self, register_type, address, count, slave_id):
        """Return fake register values."""
        registers = self._registers_by_slave[slave_id]
        return [registers.get(address + offset, 0) for offset in range(count)]

    async def async_read_device_identification(self, slave_id):
        """Return fake device identification."""
        return self._device_info_by_slave[slave_id]

    async def async_close(self) -> None:
        """Close the fake client."""
        return


class FakeWritableSerialBusModbusClient(FakeSerialBusModbusClient):
    """Fake Modbus client that records write calls."""

    instances = []

    def __init__(self, config) -> None:
        """Initialize the fake client."""
        super().__init__(config)
        self.writes = []
        self.instances.append(self)

    async def async_write_registers(self, address, values, slave_id):
        """Record a fake multiple-register write."""
        self.writes.append(("registers", slave_id, address, tuple(values)))

    async def async_write_register(self, address, value, slave_id):
        """Record a fake single-register write."""
        self.writes.append(("register", slave_id, address, value))


class FakeGatewayBusModbusClient(FakeSerialBusModbusClient):
    """Fake shared-bus client that also exposes TCP gateway metadata."""

    async def async_read_tcp_gateway_info(self):
        """Return fake TCP gateway information."""
        return IneproTcpGatewayInfo(
            device_type_code=330,
            device_type="TCP Gateway",
            hardware_version="1",
            serial_number="033023260024",
            firmware_type=5,
            firmware_version="1.0.973",
            bootloader_version="1.0.845",
        )


class FakeGatewayBusPartialProModbusClient(FakeGatewayBusModbusClient):
    """Fake TCP gateway bus where one PRO meter rejects some status blocks."""

    def __init__(self, config) -> None:
        """Initialize the fake client."""
        super().__init__(config)
        self._registers_by_slave = {
            27: _register_map_pro_380(),
        }
        self._device_info_by_slave = {
            27: IneproDeviceIdentification(
                manufacturer_name="inepro Metering B.V.",
                product_name="PRO380",
                version="V2.18",
            ),
        }

    async def async_read_registers(self, register_type, address, count, slave_id):
        """Return fake register values."""
        if slave_id == 27 and address in {0x4015, 0x401B}:
            raise IneproReadError("status block unsupported")
        return await super().async_read_registers(
            register_type, address, count, slave_id
        )


class FakeFlakyBluetoothProxyModbusClient(FakeModbusClient):
    """Fake BLE proxy client that can fail after a successful first update."""

    def __init__(self, config) -> None:
        """Initialize the fake client."""
        super().__init__(config)
        self.fail_mode: str | None = None

    async def async_read_registers(self, register_type, address, count, slave_id):
        """Return fake register values."""
        if self.fail_mode == "read_error":
            raise IneproReadError("transient ble proxy failure")
        if self.fail_mode == "short_block" and address == 0x5000:
            return [self._registers.get(address, 0)]
        return await super().async_read_registers(
            register_type, address, count, slave_id
        )


class FakeUnsupportedDeviceIdentificationModbusClient(FakeModbusClient):
    """Fake meter that rejects Modbus Read Device Identification."""

    def __init__(self, config) -> None:
        """Initialize the fake client."""
        super().__init__(config)
        self.device_identification_calls = 0

    async def async_read_device_identification(self, slave_id):
        """Return fake device identification."""
        self.device_identification_calls += 1
        raise IneproReadError("device identification unsupported")


async def test_setup_entry_creates_expected_sensor_entities(
    hass,
) -> None:
    """A config entry should create coordinator-backed GROW entities."""
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
        FakeModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.test_meter_status").state == "online"
    assert float(hass.states.get("sensor.test_meter_total_active_power").state) == 3.2
    assert (
        float(hass.states.get("sensor.test_meter_forward_active_energy").state)
        == 12.345
    )
    assert hass.states.get("sensor.test_meter_serial_number").state == "25150002"
    assert hass.states.get("sensor.test_meter_product_code").state == "0850"
    assert hass.states.get("sensor.test_meter_error_code").state == "0000"
    assert (
        hass.states.get("sensor.test_meter_error_summary").state == "No critical errors"
    )
    assert (
        hass.states.get("sensor.test_meter_manufacturer_name").state
        == "inepro Metering B.V."
    )
    assert hass.states.get("sensor.test_meter_product_name").state == "879-3120"
    assert hass.states.get("sensor.test_meter_device_version").state == "V1.0.2744"
    assert (
        hass.states.get("sensor.test_meter_legal_software_version").state == "1.0.2536"
    )
    assert (
        hass.states.get("sensor.test_meter_non_legal_software_version").state
        == "1.0.2536"
    )
    assert hass.states.get("sensor.test_meter_hardware_version").state == "2.0"

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "085025150002")})
    assert device is not None
    assert device.model == "879-3120"
    assert device.sw_version == "1.0.2536"
    assert device.hw_version == "2.0"

    # Disabled-by-default entities should not be added to the state machine.
    assert hass.states.get("sensor.test_meter_temperature") is None
    assert hass.states.get("sensor.test_meter_legal_software_crc") is None
    error_state = hass.states.get("sensor.test_meter_error_code")
    assert error_state is not None
    assert error_state.attributes["decoded_error_summary"] == "No critical errors"
    assert error_state.attributes["decoded_errors"] == []

    legal = hass.states.get("sensor.test_meter_legal_software_version")
    non_legal = hass.states.get("sensor.test_meter_non_legal_software_version")
    assert legal is not None
    assert non_legal is not None
    assert legal.attributes["raw_version"] == "1.0"
    assert legal.attributes["crc"] == "6A479857"
    assert non_legal.attributes["raw_version"] == "1.0"
    assert non_legal.attributes["crc"] == "6A479857"


async def test_setup_entry_creates_expected_pro_sensor_entities(
    hass,
) -> None:
    """A PRO config entry should create coordinator-backed serial Modbus entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PRO Meter",
        data={
            CONF_FAMILY: MeterFamily.PRO.value,
            CONF_VARIANT: "pro_380",
            CONF_TRANSPORT: TransportType.SERIAL.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            CONF_SERIAL_PORT: "COM8",
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
        FakeProModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.pro_meter_status").state == "online"
    assert float(hass.states.get("sensor.pro_meter_voltage_l1").state) == 230.1
    assert float(hass.states.get("sensor.pro_meter_current_l3").state) == 10.2
    assert float(hass.states.get("sensor.pro_meter_total_active_power").state) == 6.789
    assert (
        float(hass.states.get("sensor.pro_meter_total_active_energy").state) == 1234.567
    )
    assert hass.states.get("sensor.pro_meter_serial_number").state == "12345678"
    assert hass.states.get("sensor.pro_meter_protocol_version").state == "2.18"
    assert hass.states.get("sensor.pro_meter_software_version").state == "2.18"
    assert hass.states.get("sensor.pro_meter_hardware_version").state == "1.02"
    assert hass.states.get("sensor.pro_meter_product_name").state == "PRO380"

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "12345678")})
    assert device is not None
    assert device.model == "PRO380"
    assert device.serial_number == "12345678"
    assert device.sw_version == "V2.18"
    assert device.hw_version == "1.02"


async def test_unknown_crc_is_reflected_in_version_strings(
    hass,
) -> None:
    """Unknown CRCs should remain visible in firmware version strings."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="CRC Meter",
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
        FakeModbusClientUnknownCrc,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    legal = hass.states.get("sensor.crc_meter_legal_software_version")
    non_legal = hass.states.get("sensor.crc_meter_non_legal_software_version")
    assert legal is not None
    assert non_legal is not None
    assert legal.state == "1.0 (B478FEE9)"
    assert non_legal.state == "1.0 (B999F660)"
    assert legal.attributes["raw_version"] == "1.0"
    assert legal.attributes["crc"] == "B478FEE9"
    assert non_legal.attributes["raw_version"] == "1.0"
    assert non_legal.attributes["crc"] == "B999F660"

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "085025150002")})
    assert device is not None
    assert device.sw_version == "legal 1.0 (B478FEE9) / non-legal 1.0 (B999F660)"


async def test_tcp_gateway_entry_exposes_gateway_diagnostic_sensors(
    hass,
) -> None:
    """A TCP gateway route should expose the gateway metadata as diagnostic sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gateway Meter",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_850",
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            "host": "10.5.2.1",
            "port": 502,
            CONF_TIMEOUT: 3,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.inepro_metering.coordinator.IneproModbusClient",
        FakeGatewayModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.inepro_gateway_033023260122_device_type").state
        == "TCP Gateway"
    )
    assert (
        hass.states.get("sensor.inepro_gateway_033023260122_hardware_version").state
        == "1"
    )
    assert (
        hass.states.get("sensor.inepro_gateway_033023260122_serial_number").state
        == "033023260122"
    )
    assert (
        hass.states.get("sensor.inepro_gateway_033023260122_firmware_version").state
        == "1.0.973"
    )
    assert (
        hass.states.get("sensor.inepro_gateway_033023260122_bootloader_version").state
        == "1.0.845"
    )

    gateway_device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, "033023260122")}
    )
    meter_device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, "085025150002")}
    )
    assert gateway_device is not None
    assert gateway_device.identifiers == {(DOMAIN, "033023260122")}
    assert gateway_device.model == "TCP Gateway"
    assert gateway_device.name == "Inepro Gateway 033023260122"
    assert gateway_device.serial_number == "033023260122"
    assert gateway_device.sw_version == "1.0.973"
    assert gateway_device.hw_version == "1"
    assert meter_device is not None
    assert meter_device.via_device_id == gateway_device.id


async def test_grow_fault_error_summary_decodes_bitfield(
    hass,
) -> None:
    """The GROW error summary sensor should decode active fault bits."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Fault Meter",
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
        FakeModbusClientFault,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    error_code = hass.states.get("sensor.fault_meter_error_code")
    error_summary = hass.states.get("sensor.fault_meter_error_summary")
    assert error_code is not None
    assert error_summary is not None
    assert error_code.state == "00C4"
    assert error_summary.state == (
        "calibration data corruption, counter journal corruption, provisioning data invalid"
    )
    assert error_code.attributes["decoded_errors"] == [
        "calibration data corruption",
        "counter journal corruption",
        "provisioning data invalid",
    ]


async def test_serial_bus_entry_creates_multiple_meter_devices(
    hass,
) -> None:
    """One serial bus entry should expose multiple configured Inepro devices."""
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
                    "name": "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SLAVE_ID: 157,
                    "serial_number": "075625480002",
                    "product_code": "0756",
                },
            ],
        },
        version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.inepro_metering.coordinator.IneproModbusClient",
        FakeSerialBusModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.085125250008_status").state == "online"
    assert hass.states.get("sensor.075625480002_status").state == "online"
    assert (
        float(hass.states.get("sensor.085125250008_average_voltage_ln").state) == 230.5
    )
    assert (
        hass.states.get("sensor.085125250008_error_summary").state
        == "No critical errors"
    )
    assert (
        hass.states.get("sensor.075625480002_error_summary").state
        == "No critical errors"
    )
    assert (
        float(hass.states.get("sensor.075625480002_average_voltage_ln").state) == 236.9
    )
    assert float(hass.states.get("sensor.075625480002_voltage_l1").state) == 236.7
    assert hass.states.get("sensor.085125250008_product_name").state == "879-3121"
    assert hass.states.get("sensor.075625480002_product_name").state == "879-3120"
    assert hass.states.get("sensor.075625480002_device_version").state == "V1.0.2744"
    assert (
        hass.states.get("sensor.075625480002_legal_software_version").state
        == "1.0 (B478FEE9)"
    )
    assert hass.states.get("sensor.075625480002_wi_fi_support").state == "enabled"
    assert hass.states.get("switch.075625480002_wi_fi_support").state == "on"
    assert hass.states.get("switch.085125250008_wi_fi_support") is None

    device_registry = dr.async_get(hass)
    single_phase = device_registry.async_get_device(
        identifiers={(DOMAIN, "085125250008")}
    )
    three_phase = device_registry.async_get_device(
        identifiers={(DOMAIN, "075625480002")}
    )
    assert single_phase is not None
    assert three_phase is not None
    assert single_phase.model == "879-3121"
    assert three_phase.model == "879-3120"
    assert single_phase.via_device_id is None
    assert three_phase.via_device_id is None


async def test_tcp_gateway_bus_entry_exposes_bus_level_gateway_device(
    hass,
) -> None:
    """A shared TCP gateway bus should expose one separate gateway device and sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gateway Bus",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            CONF_SCAN_INTERVAL: 15,
            "host": "10.5.2.14",
            "port": 502,
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
                    "name": "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SLAVE_ID: 157,
                    "serial_number": "075625480002",
                    "product_code": "0756",
                },
            ],
        },
        version=5,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.inepro_metering.coordinator.IneproModbusClient",
        FakeGatewayBusModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.inepro_gateway_033023260024_device_type").state
        == "TCP Gateway"
    )
    assert (
        hass.states.get("sensor.inepro_gateway_033023260024_hardware_version").state
        == "1"
    )
    assert (
        hass.states.get("sensor.inepro_gateway_033023260024_serial_number").state
        == "033023260024"
    )
    assert hass.states.get("sensor.085125250008_status").state == "online"
    assert hass.states.get("sensor.075625480002_status").state == "online"

    gateway_device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, "033023260024")}
    )
    single_phase = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, "085125250008")}
    )
    three_phase = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, "075625480002")}
    )
    assert gateway_device is not None
    assert gateway_device.identifiers == {(DOMAIN, "033023260024")}
    assert gateway_device.model == "TCP Gateway"
    assert gateway_device.name == "Inepro Gateway 033023260024"
    assert gateway_device.serial_number == "033023260024"
    assert gateway_device.hw_version == "1"
    assert single_phase is not None
    assert three_phase is not None
    assert single_phase.via_device_id == gateway_device.id
    assert three_phase.via_device_id == gateway_device.id


async def test_tcp_gateway_bus_keeps_meter_online_when_status_blocks_fail(
    hass,
) -> None:
    """A gateway meter should stay online when only optional status blocks fail."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="025715120327",
        data={
            CONF_FAMILY: MeterFamily.PRO.value,
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            CONF_SCAN_INTERVAL: 15,
            "host": "192.168.67.16",
            "port": 502,
            CONF_TIMEOUT: 10,
            CONF_METERS: [
                {
                    "family": MeterFamily.PRO.value,
                    "name": "025715120327",
                    CONF_VARIANT: "pro_380",
                    CONF_SLAVE_ID: 27,
                    "serial_number": "025715120327",
                    "product_code": "0257",
                },
            ],
        },
        version=5,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.inepro_metering.coordinator.IneproModbusClient",
        FakeGatewayBusPartialProModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.025715120327_status").state == "online"
    assert float(
        hass.states.get("sensor.025715120327_total_active_power").state
    ) == pytest.approx(6.789)
    assert hass.states.get("sensor.025715120327_error_code").state == "unknown"


async def test_tcp_gateway_bus_entry_with_no_meters_loads_gateway_device(
    hass,
) -> None:
    """A verified TCP gateway with no meters should still load as a device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Inepro Gateway 192.168.68.85:502",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            CONF_SCAN_INTERVAL: 15,
            "host": "192.168.68.85",
            "port": 502,
            CONF_TIMEOUT: 3,
            CONF_METERS: [],
        },
        version=5,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.inepro_metering.coordinator.IneproModbusClient",
        FakeGatewayBusModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.title == "Inepro Gateway 033023260024"
    assert (
        hass.states.get("sensor.inepro_gateway_033023260024_device_type").state
        == "TCP Gateway"
    )
    assert (
        hass.states.get("sensor.inepro_gateway_033023260024_serial_number").state
        == "033023260024"
    )

    gateway_device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, "033023260024")}
    )
    assert gateway_device is not None
    assert gateway_device.model == "TCP Gateway"
    assert gateway_device.name == "Inepro Gateway 033023260024"
    assert gateway_device.serial_number == "033023260024"


async def test_coordinator_skips_unsupported_modbus_device_identification(
    hass,
) -> None:
    """Unsupported 43/14 metadata reads should not poison later polls."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="GROW Wi-Fi Meter",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.TCP_WIFI.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            "host": "192.0.2.55",
            "port": 502,
            CONF_TIMEOUT: 3,
        },
    )

    with patch(
        "homeassistant.components.inepro_metering.coordinator.IneproModbusClient",
        FakeUnsupportedDeviceIdentificationModbusClient,
    ):
        coordinator = IneproMeteringCoordinator(hass, entry)
        first = await coordinator._async_update_data()
        second = await coordinator._async_update_data()
        client = coordinator._client

    assert isinstance(client, FakeUnsupportedDeviceIdentificationModbusClient)
    assert client.device_identification_calls == 1
    assert first.meter.connection.available is True
    assert second.meter.connection.available is True
    assert first.readings["serial_number"] == "25150002"
    assert second.readings["serial_number"] == "25150002"


async def test_bluetooth_proxy_coordinator_keeps_last_data_on_transient_failures(
    hass,
) -> None:
    """Transient Bluetooth proxy failures should reuse the last successful data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BLE Meter",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.BLUETOOTH_PROXY.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            "host": "172.28.224.1",
            "port": 15026,
            "bluetooth_address": "80:F1:B2:58:DD:5A",
            "bluetooth_name": "IM-075625480002",
            CONF_TIMEOUT: 3,
        },
    )

    with patch(
        "homeassistant.components.inepro_metering.coordinator.IneproModbusClient",
        FakeFlakyBluetoothProxyModbusClient,
    ):
        coordinator = IneproMeteringCoordinator(hass, entry)
        first = await coordinator._async_update_data()
        client = coordinator._client
        assert isinstance(client, FakeFlakyBluetoothProxyModbusClient)

        client.fail_mode = "read_error"
        second = await coordinator._async_update_data()
        third = await coordinator._async_update_data()
        fourth = await coordinator._async_update_data()

        assert second.readings == first.readings
        assert third.readings == first.readings
        assert fourth.readings == first.readings
        assert second.last_successful_update == first.last_successful_update

        with pytest.raises(UpdateFailed, match="transient ble proxy failure"):
            await coordinator._async_update_data()


async def test_bluetooth_proxy_coordinator_keeps_last_data_on_short_payloads(
    hass,
) -> None:
    """Short malformed BLE payloads should not immediately blank a working meter."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BLE Meter",
        data={
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_VARIANT: "grow_750",
            CONF_TRANSPORT: TransportType.BLUETOOTH_PROXY.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            "host": "172.28.224.1",
            "port": 15026,
            "bluetooth_address": "80:F1:B2:58:DD:5A",
            "bluetooth_name": "IM-075625480002",
            CONF_TIMEOUT: 3,
        },
    )

    with patch(
        "homeassistant.components.inepro_metering.coordinator.IneproModbusClient",
        FakeFlakyBluetoothProxyModbusClient,
    ):
        coordinator = IneproMeteringCoordinator(hass, entry)
        first = await coordinator._async_update_data()
        client = coordinator._client
        assert isinstance(client, FakeFlakyBluetoothProxyModbusClient)

        client.fail_mode = "short_block"
        second = await coordinator._async_update_data()

        assert second.readings == first.readings
        assert second.last_successful_update == first.last_successful_update


async def test_set_wifi_credentials_service_writes_grow_register_sequence(
    hass,
) -> None:
    """The Wi-Fi service should write SSID, password, then the apply command."""
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
                    "name": "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SLAVE_ID: 157,
                    "serial_number": "075625480002",
                    "product_code": "0756",
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
        await hass.services.async_call(
            DOMAIN,
            "set_wifi_credentials",
            {
                "serial_number": "075625480002",
                "ssid": "IneproLab",
                "password": "secret",
                "apply": True,
            },
            blocking=True,
        )

    client = FakeWritableSerialBusModbusClient.instances[0]
    assert len(client.writes) == 4
    assert client.writes[0] == ("register", 157, WIFI_ENABLE_ADDRESS, 1)
    assert client.writes[1][:3] == ("registers", 157, WIFI_SSID_ADDRESS)
    assert client.writes[1][3][:5] == (0x496E, 0x6570, 0x726F, 0x4C61, 0x6200)
    assert client.writes[2][:3] == ("registers", 157, WIFI_PASSWORD_ADDRESS)
    assert client.writes[2][3][:3] == (0x7365, 0x6372, 0x6574)
    assert client.writes[3] == ("registers", 157, WIFI_APPLY_ADDRESS, (1,))


async def test_set_wifi_credentials_service_rejects_unknown_serial_before_write(
    hass,
) -> None:
    """Unknown serials should fail service validation before any meter write."""
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
                    "name": "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SLAVE_ID: 157,
                    "serial_number": "075625480002",
                    "product_code": "0756",
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
        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "set_wifi_credentials",
                {
                    "serial_number": "000000000000",
                    "ssid": "IneproLab",
                    "password": "secret",
                    "apply": False,
                },
                blocking=True,
            )

    err = exc_info.value
    assert err.translation_domain == DOMAIN
    assert err.translation_key == EXC_WIFI_CREDENTIALS_METER_NOT_FOUND
    assert err.translation_placeholders == {"serial_number": "000000000000"}
    client = FakeWritableSerialBusModbusClient.instances[0]
    assert client.writes == []


async def test_set_wifi_credentials_service_rejects_invalid_credentials_before_write(
    hass,
) -> None:
    """Invalid credential data should become a translated validation error."""
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
                    "name": "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SLAVE_ID: 157,
                    "serial_number": "075625480002",
                    "product_code": "0756",
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
        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "set_wifi_credentials",
                {
                    "serial_number": "075625480002",
                    "ssid": "",
                    "password": "secret",
                    "apply": False,
                },
                blocking=True,
            )

    err = exc_info.value
    assert err.translation_domain == DOMAIN
    assert err.translation_key == EXC_WIFI_CREDENTIALS_INVALID
    assert err.translation_placeholders == {"error": "SSID must not be empty"}
    client = FakeWritableSerialBusModbusClient.instances[0]
    assert client.writes == []


async def test_wifi_support_switch_toggles_confirmed_register(
    hass,
) -> None:
    """The Wi-Fi support switch should write the confirmed enable register."""
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
                    "name": "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SLAVE_ID: 157,
                    "serial_number": "075625480002",
                    "product_code": "0756",
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
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_off",
            {"entity_id": "switch.075625480002_wi_fi_support"},
            blocking=True,
        )
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_on",
            {"entity_id": "switch.075625480002_wi_fi_support"},
            blocking=True,
        )

    client = FakeWritableSerialBusModbusClient.instances[0]
    assert client.writes[-2:] == [
        ("register", 157, WIFI_ENABLE_ADDRESS, 0),
        ("register", 157, WIFI_ENABLE_ADDRESS, 1),
    ]


async def test_set_wifi_credentials_service_rejects_non_wifi_model(
    hass,
) -> None:
    """The Wi-Fi service should reject GROW models without Wi-Fi support."""
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
                    "name": "075625480002",
                    CONF_VARIANT: "grow_750",
                    CONF_SLAVE_ID: 157,
                    "serial_number": "075625480002",
                    "product_code": "0756",
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
        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "set_wifi_credentials",
                {
                    "serial_number": "085125250008",
                    "ssid": "IneproLab",
                    "password": "secret",
                },
                blocking=True,
            )

    err = exc_info.value
    assert err.translation_domain == DOMAIN
    assert err.translation_key == EXC_WIFI_CREDENTIALS_UNSUPPORTED
    assert err.translation_placeholders == {
        "serial_number": "085125250008",
        "model": "GROW 1P1U",
    }
    client = FakeWritableSerialBusModbusClient.instances[0]
    assert client.writes == []
