"""Home Assistant tests for TCP gateway configuration entities."""

import ipaddress
from unittest.mock import patch

from inepro_metering.commands import encode_ascii_registers
from inepro_metering.const import MeterFamily, TransportType
from inepro_metering.gateway_settings import (
    CONFIG_DHCP_ENABLED,
    CONFIG_DNS_SERVER_HIGH,
    CONFIG_GATEWAY_HIGH,
    CONFIG_HOSTNAME_START,
    CONFIG_IP_HIGH,
    CONFIG_MODBUS_BAUDRATE,
    CONFIG_MODBUS_DEVICEID,
    CONFIG_MODBUS_PARITY,
    CONFIG_MODBUS_TIMEOUT,
    CONFIG_MODBUS_UART_DEVICE,
    CONFIG_NETMASK_HIGH,
    CONFIG_NTP_SERVER_HIGH,
    CONFIG_NTP_SUPPORT_ENABLED,
    CONFIG_SECONDARY_DNS_SERVER_HIGH,
    CONFIG_SECONDARY_NTP_SERVER_HIGH,
    GATEWAY_ACTIONS,
    GATEWAY_MANAGEMENT_SLAVE_ID,
    GATEWAY_SETTINGS,
    HOSTNAME_REGISTER_COUNT,
    SETTINGS_APPLY,
    SETTINGS_REVERT,
    SETTINGS_STORE,
    decode_gateway_configuration_registers,
)
from inepro_metering.modbus import IneproDeviceIdentification, IneproTcpGatewayInfo
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.inepro_metering.const import (
    CONF_FAMILY,
    CONF_METERS,
    CONF_SLAVE_ID,
    CONF_TRANSPORT,
    CONF_VARIANT,
    DOMAIN,
)
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.text import DOMAIN as TEXT_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


def _encode_ipv4_words(value: str) -> tuple[int, int]:
    """Encode one IPv4 address into the vendor high/low word layout."""
    address = int(ipaddress.IPv4Address(value))
    return ((address >> 16) & 0xFFFF, address & 0xFFFF)


def _gateway_entity_id(hass, platform: str, entry_id: str, key: str) -> str:
    """Resolve one gateway config entity ID from its preserved unique ID pattern."""
    entity_id = er.async_get(hass).async_get_entity_id(
        platform,
        DOMAIN,
        f"{entry_id}_gateway_{key}_{platform}",
    )
    assert entity_id is not None
    return entity_id


class FakeGatewayConfigModbusClient:
    """Stateful fake Modbus client for gateway configuration entity tests."""

    instances: list[FakeGatewayConfigModbusClient] = []

    def __init__(self, config) -> None:
        """Initialize the fake client."""
        del config
        self._modbus_registers = [0] * 5
        self._network_registers = [0] * 32
        self.writes: list[tuple[int, int, tuple[int, ...], bool]] = []
        self.instances.append(self)

        self._set_modbus_value(CONFIG_MODBUS_BAUDRATE, 6)
        self._set_modbus_value(CONFIG_MODBUS_PARITY, 1)
        self._set_modbus_value(CONFIG_MODBUS_UART_DEVICE, 2)
        self._set_modbus_value(CONFIG_MODBUS_TIMEOUT, 500)
        self._set_network_value(CONFIG_DHCP_ENABLED, 1)
        self._set_network_value(CONFIG_NTP_SUPPORT_ENABLED, 0)
        self._set_ipv4(CONFIG_IP_HIGH, "192.0.2.10")
        self._set_ipv4(CONFIG_NETMASK_HIGH, "255.255.255.0")
        self._set_ipv4(CONFIG_GATEWAY_HIGH, "192.0.2.1")
        self._set_ipv4(CONFIG_DNS_SERVER_HIGH, "1.1.1.1")
        self._set_ipv4(CONFIG_SECONDARY_DNS_SERVER_HIGH, "9.9.9.9")
        self._set_ipv4(CONFIG_NTP_SERVER_HIGH, "129.6.15.28")
        self._set_ipv4(CONFIG_SECONDARY_NTP_SERVER_HIGH, "132.163.96.1")
        self._set_hostname("GATEWAY-01")

    def _set_modbus_value(self, address: int, value: int) -> None:
        self._modbus_registers[address - CONFIG_MODBUS_BAUDRATE] = int(value) & 0xFFFF

    def _set_network_value(self, address: int, value: int) -> None:
        self._network_registers[address - CONFIG_IP_HIGH] = int(value) & 0xFFFF

    def _set_ipv4(self, address: int, value: str) -> None:
        high_word, low_word = _encode_ipv4_words(value)
        self._set_network_value(address, high_word)
        self._set_network_value(address + 1, low_word)

    def _set_hostname(self, value: str) -> None:
        words = encode_ascii_registers(
            value,
            register_count=HOSTNAME_REGISTER_COUNT,
            field_name="Host name",
        )
        for offset, word in enumerate(words):
            self._set_network_value(CONFIG_HOSTNAME_START + offset, word)

    def _apply_write(self, address: int, values: tuple[int, ...]) -> None:
        for offset, value in enumerate(values):
            current_address = address + offset
            if CONFIG_MODBUS_BAUDRATE <= current_address <= CONFIG_MODBUS_DEVICEID:
                self._set_modbus_value(current_address, value)
                continue
            if (
                CONFIG_IP_HIGH
                <= current_address
                < CONFIG_IP_HIGH + len(self._network_registers)
            ):
                self._set_network_value(current_address, value)

    async def async_read_registers(self, register_type, address, count, slave_id):
        """Return fake register values."""
        del register_type, address, slave_id
        return [0] * count

    async def async_read_device_identification(self, slave_id):
        """Return fake device identification."""
        del slave_id
        return IneproDeviceIdentification(
            manufacturer_name="inepro Metering B.V.",
            product_name="PRO380",
            version="V2.18",
        )

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

    async def async_read_tcp_gateway_configuration(self):
        """Return fake TCP gateway configuration."""
        return decode_gateway_configuration_registers(
            modbus_registers=self._modbus_registers,
            network_registers=self._network_registers,
        )

    async def async_write_register(self, address, value, slave_id):
        """Record a fake single-register write."""
        normalized = (int(value),)
        self.writes.append((slave_id, address, normalized, False))
        self._apply_write(address, normalized)

    async def async_write_registers(self, address, values, slave_id):
        """Record a fake multiple-register write."""
        normalized = tuple(int(value) for value in values)
        self.writes.append((slave_id, address, normalized, True))
        self._apply_write(address, normalized)

    async def async_close(self) -> None:
        """Close the fake client."""
        return


async def test_tcp_gateway_entry_exposes_gateway_only_configuration_entities(
    hass,
) -> None:
    """Gateway-backed entries should expose the confirmed gateway config surfaces."""
    FakeGatewayConfigModbusClient.instances.clear()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gateway Config",
        data={
            CONF_FAMILY: MeterFamily.PRO.value,
            CONF_VARIANT: "pro_380",
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            "host": "10.5.2.10",
            "port": 502,
            CONF_TIMEOUT: 3,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.inepro_metering.coordinator.IneproModbusClient",
        FakeGatewayConfigModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.get(
            _gateway_entity_id(hass, SWITCH_DOMAIN, entry.entry_id, "dhcp_enabled")
        ).state
        == "on"
    )
    assert (
        hass.states.get(
            _gateway_entity_id(hass, SWITCH_DOMAIN, entry.entry_id, "ntp_enabled")
        ).state
        == "off"
    )
    assert (
        hass.states.get(
            _gateway_entity_id(hass, SELECT_DOMAIN, entry.entry_id, "modbus_port")
        ).state
        == "RS485"
    )
    assert (
        hass.states.get(
            _gateway_entity_id(hass, SELECT_DOMAIN, entry.entry_id, "baudrate")
        ).state
        == "9600"
    )
    assert (
        hass.states.get(
            _gateway_entity_id(hass, SELECT_DOMAIN, entry.entry_id, "parity")
        ).state
        == "EVEN"
    )
    assert (
        float(
            hass.states.get(
                _gateway_entity_id(hass, NUMBER_DOMAIN, entry.entry_id, "timeout_ms")
            ).state
        )
        == 500.0
    )
    assert (
        hass.states.get(
            _gateway_entity_id(hass, TEXT_DOMAIN, entry.entry_id, "ip_address")
        ).state
        == "192.0.2.10"
    )
    assert (
        hass.states.get(
            _gateway_entity_id(hass, TEXT_DOMAIN, entry.entry_id, "host_name")
        ).state
        == "GATEWAY-01"
    )
    assert (
        hass.states.get(
            _gateway_entity_id(hass, TEXT_DOMAIN, entry.entry_id, "ntp_server_1")
        ).state
        == "129.6.15.28"
    )
    assert (
        hass.states.get(
            _gateway_entity_id(hass, BUTTON_DOMAIN, entry.entry_id, "apply")
        ).state
        == "unknown"
    )


async def test_gateway_text_entity_rejects_invalid_ipv4_before_write(
    hass,
) -> None:
    """Gateway IPv4 text writes should fail before any Modbus write is attempted."""
    FakeGatewayConfigModbusClient.instances.clear()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gateway Validation",
        data={
            CONF_FAMILY: MeterFamily.PRO.value,
            CONF_VARIANT: "pro_380",
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            "host": "10.5.2.11",
            "port": 502,
            CONF_TIMEOUT: 3,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.inepro_metering.coordinator.IneproModbusClient",
        FakeGatewayConfigModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(ValueError, match="IP address must be a valid IPv4 address"):
            await hass.services.async_call(
                TEXT_DOMAIN,
                "set_value",
                {
                    "entity_id": _gateway_entity_id(
                        hass,
                        TEXT_DOMAIN,
                        entry.entry_id,
                        "ip_address",
                    ),
                    "value": "300.1.2.3",
                },
                blocking=True,
            )

    assert FakeGatewayConfigModbusClient.instances[0].writes == []


async def test_gateway_buttons_preserve_revert_apply_store_sequence(
    hass,
) -> None:
    """Gateway action buttons should route the confirmed ordered write plans."""
    FakeGatewayConfigModbusClient.instances.clear()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gateway Actions",
        data={
            CONF_FAMILY: MeterFamily.PRO.value,
            CONF_VARIANT: "pro_380",
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            CONF_SLAVE_ID: 1,
            CONF_SCAN_INTERVAL: 15,
            "host": "10.5.2.12",
            "port": 502,
            CONF_TIMEOUT: 3,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.inepro_metering.coordinator.IneproModbusClient",
        FakeGatewayConfigModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {
                "entity_id": _gateway_entity_id(
                    hass, BUTTON_DOMAIN, entry.entry_id, "revert"
                )
            },
            blocking=True,
        )
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {
                "entity_id": _gateway_entity_id(
                    hass, BUTTON_DOMAIN, entry.entry_id, "apply"
                )
            },
            blocking=True,
        )
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {
                "entity_id": _gateway_entity_id(
                    hass,
                    BUTTON_DOMAIN,
                    entry.entry_id,
                    "apply_and_store",
                )
            },
            blocking=True,
        )

    assert FakeGatewayConfigModbusClient.instances[0].writes == [
        (GATEWAY_MANAGEMENT_SLAVE_ID, SETTINGS_REVERT, (1,), False),
        (GATEWAY_MANAGEMENT_SLAVE_ID, SETTINGS_APPLY, (1,), False),
        (GATEWAY_MANAGEMENT_SLAVE_ID, SETTINGS_STORE, (1,), False),
        (GATEWAY_MANAGEMENT_SLAVE_ID, SETTINGS_APPLY, (1,), False),
    ]


async def test_gateway_config_entities_are_created_once_for_the_gateway_device(
    hass,
) -> None:
    """Gateway config entities should attach once to the gateway, not downstream meters."""
    FakeGatewayConfigModbusClient.instances.clear()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gateway Bus",
        data={
            CONF_FAMILY: MeterFamily.PRO.value,
            CONF_TRANSPORT: TransportType.TCP_GATEWAY.value,
            CONF_SCAN_INTERVAL: 15,
            "host": "10.5.2.14",
            "port": 502,
            CONF_TIMEOUT: 3,
            CONF_METERS: [
                {
                    "name": "12345678",
                    CONF_VARIANT: "pro_1",
                    CONF_SLAVE_ID: 1,
                    "serial_number": "12345678",
                },
                {
                    "name": "87654321",
                    CONF_VARIANT: "pro_380",
                    CONF_SLAVE_ID: 157,
                    "serial_number": "87654321",
                },
            ],
        },
        version=5,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.inepro_metering.coordinator.IneproModbusClient",
        FakeGatewayConfigModbusClient,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    gateway_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "033023260122")}
    )
    assert gateway_device is not None

    gateway_entity_entries = [
        entity
        for entity in entity_registry.entities.values()
        if entity.platform == DOMAIN
        and entity.unique_id.startswith(f"{entry.entry_id}_gateway_")
        and entity.domain
        in {
            SWITCH_DOMAIN,
            SELECT_DOMAIN,
            NUMBER_DOMAIN,
            TEXT_DOMAIN,
            BUTTON_DOMAIN,
        }
    ]

    assert len(gateway_entity_entries) == len(GATEWAY_SETTINGS) + len(GATEWAY_ACTIONS)
    assert {entity.device_id for entity in gateway_entity_entries} == {
        gateway_device.id
    }
