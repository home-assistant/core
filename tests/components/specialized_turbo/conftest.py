"""Fixtures for Specialized Turbo integration tests."""

import base64
from collections.abc import Generator
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import pytest
from specialized_turbo import PRODUCTION_WRAPPING_KEY, AssistLevel, TelemetrySnapshot

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.specialized_turbo.const import (
    CONF_HMI_HARDWARE,
    CONF_HMI_SERIAL,
    CONF_KEY_SOURCE,
    CONF_WRAPPED_KEY,
    DOMAIN,
    KEY_SOURCE_MANUAL,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

MOCK_ADDRESS = "DC:DD:BB:4A:D6:55"
MOCK_ADDRESS_FORMATTED = "dc:dd:bb:4a:d6:55"
MOCK_NAME = "SPECIALIZED"
MOCK_MANUFACTURER_DATA: dict[int, bytes] = {0x0059: b"TURBOHMItest1234"}
MOCK_ENCRYPTED_MANUFACTURER_DATA: dict[int, bytes] = {
    0x0059: bytes.fromhex("dac8c404423333330601")
}

MOCK_TCU1_ADDRESS = "C6:1A:10:12:5E:48"
MOCK_TCU1_ADDRESS_FORMATTED = "c6:1a:10:12:5e:48"
MOCK_TCU1_MANUFACTURER_DATA: dict[int, bytes] = {
    0x020D: bytes.fromhex("028657" + "ff" * 24),
}


def make_service_info(
    *,
    name: str = MOCK_NAME,
    address: str = MOCK_ADDRESS,
    manufacturer_data: dict[int, bytes] | None = None,
    service_uuids: list[str] | None = None,
    time: float = 0,
) -> BluetoothServiceInfoBleak:
    """Build Bluetooth service information for a bike."""
    manufacturer_data = (
        MOCK_MANUFACTURER_DATA if manufacturer_data is None else manufacturer_data
    )
    service_uuids = service_uuids or []
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        device=generate_ble_device(address=address, name=name),
        rssi=-61,
        manufacturer_data=manufacturer_data,
        service_data={},
        service_uuids=service_uuids,
        source="local",
        advertisement=generate_advertisement_data(
            manufacturer_data=manufacturer_data,
            service_uuids=service_uuids,
        ),
        connectable=True,
        time=time,
        tx_power=None,
    )


TCX_SERVICE_INFO = make_service_info()
ENCRYPTED_SERVICE_INFO = make_service_info(
    manufacturer_data=MOCK_ENCRYPTED_MANUFACTURER_DATA
)
TCU1_SERVICE_INFO = make_service_info(
    address=MOCK_TCU1_ADDRESS,
    manufacturer_data=MOCK_TCU1_MANUFACTURER_DATA,
)
NAME_ONLY_SERVICE_INFO = make_service_info(
    name="WSBC025079419R",
    manufacturer_data={},
)


def make_wrapped_key(
    key: bytes = bytes.fromhex("00112233445566778899aabbccddeeff"),
) -> str:
    """Build a valid wrapped key for config flow tests."""
    wrapping_iv = bytes(range(16))
    cipher = Cipher(
        algorithms.AES(PRODUCTION_WRAPPING_KEY),
        modes.CTR(wrapping_iv),
    )
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(key.hex().encode()) + encryptor.finalize()
    return base64.b64encode(wrapping_iv + encrypted).decode()


def make_populated_snapshot() -> TelemetrySnapshot:
    """Build a snapshot containing values for every sensor."""
    snapshot = TelemetrySnapshot()
    snapshot.message_count = 1
    snapshot.battery.charge_pct = 85
    snapshot.battery.capacity_wh = 700
    snapshot.battery.remaining_wh = 500
    snapshot.battery.health_pct = 95
    snapshot.battery.temp_c = 24
    snapshot.battery.charge_cycles = 12
    snapshot.battery.voltage_v = 48.2
    snapshot.battery.current_a = -3.4
    snapshot.motor.speed_kmh = 25.5
    snapshot.motor.rider_power_w = 120
    snapshot.motor.motor_power_w = 250
    snapshot.motor.cadence_rpm = 82
    snapshot.motor.odometer_km = 1234.5
    snapshot.motor.motor_temp_c = 42
    snapshot.motor.assist_level = AssistLevel.TRAIL
    snapshot.settings.assist_lev1_pct = 35
    snapshot.settings.assist_lev2_pct = 70
    snapshot.settings.assist_lev3_pct = 100
    snapshot.system.range_long_km = 80
    snapshot.system.range_short_km = 35
    snapshot.system.altitude_m = 123
    snapshot.system.altitude_gain_m = 456
    snapshot.system.gradient_pct = 3.5
    snapshot.system.system_temp_c = 31
    snapshot.system.consumption_wh_km = 8.2
    snapshot.system.kcal = 640
    return snapshot


@dataclass
class MockLibrary:
    """Mocks for the specialized-turbo runtime boundary."""

    connection: MagicMock
    monitor: MagicMock
    connection_constructor: MagicMock
    monitor_constructor: MagicMock


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Enable the mocked Bluetooth integration."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        title="Mock title",
        data={CONF_ADDRESS: MOCK_ADDRESS},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )


@pytest.fixture
def encrypted_config_entry() -> MockConfigEntry:
    """Create an encrypted-bike config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        title="Mock title",
        data={
            CONF_ADDRESS: MOCK_ADDRESS,
            CONF_HMI_HARDWARE: "B.3.3",
            CONF_HMI_SERIAL: "80005338",
            CONF_KEY_SOURCE: KEY_SOURCE_MANUAL,
            CONF_WRAPPED_KEY: make_wrapped_key(),
        },
        unique_id=MOCK_ADDRESS_FORMATTED,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent entry setup during config flow tests."""

    async def setup_entry(
        _hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> bool:
        runtime_data = MagicMock()
        runtime_data.async_shutdown = AsyncMock()
        entry.runtime_data = runtime_data
        return True

    with patch(
        "homeassistant.components.specialized_turbo.async_setup_entry",
        side_effect=setup_entry,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_library() -> Generator[MockLibrary]:
    """Mock the library boundary while retaining integration behavior."""
    connection = MagicMock()
    connection.is_connected = False

    async def connect() -> None:
        connection.is_connected = True

    async def disconnect() -> None:
        connection.is_connected = False

    connection.connect = AsyncMock(side_effect=connect)
    connection.disconnect = AsyncMock(side_effect=disconnect)

    monitor = MagicMock()
    monitor.snapshot = TelemetrySnapshot()
    monitor.start = AsyncMock()
    monitor.stop = AsyncMock()
    monitor.poll = AsyncMock(return_value=True)

    connection_constructor = MagicMock(return_value=connection)
    monitor_constructor = MagicMock(return_value=monitor)

    with (
        patch(
            "homeassistant.components.specialized_turbo.config_flow.async_ble_device_from_address",
            return_value=TCX_SERVICE_INFO.device,
        ),
        patch(
            "homeassistant.components.specialized_turbo.config_flow.SpecializedConnection",
            new=connection_constructor,
        ),
        patch(
            "homeassistant.components.specialized_turbo.coordinator.SpecializedConnection",
            new=connection_constructor,
        ),
        patch(
            "homeassistant.components.specialized_turbo.coordinator.TelemetryMonitor",
            new=monitor_constructor,
        ),
    ):
        yield MockLibrary(
            connection=connection,
            monitor=monitor,
            connection_constructor=connection_constructor,
            monitor_constructor=monitor_constructor,
        )
