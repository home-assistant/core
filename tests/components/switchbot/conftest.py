"""Define fixtures available for all tests."""

import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.switchbot.const import (
    CONF_CURTAIN_SPEED,
    CONF_ENCRYPTION_KEY,
    CONF_KEY_ID,
    CONF_RETRY_COUNT,
    DEFAULT_CURTAIN_SPEED,
    DEFAULT_RETRY_COUNT,
    DOMAIN,
    SupportedModels,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_SENSOR_TYPE

from . import WOSENSORTH_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_ble_device


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def meter_service_info() -> BluetoothServiceInfoBleak:
    """Return a Meter advertisement with a normalized Bluetooth address."""
    return BluetoothServiceInfoBleak.from_device_and_advertisement_data(
        generate_ble_device("AA:BB:CC:DD:EE:FF", "WoSensorTH"),
        WOSENSORTH_SERVICE_INFO.advertisement,
        source="local",
        connectable=False,
        time=0,
    )


@pytest.fixture
def mock_entry_factory():
    """Fixture to create a MockConfigEntry with a customizable sensor type."""

    def _create_entry(sensor_type: str = "curtain") -> MockConfigEntry:
        options: dict[str, int] = {CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT}
        if sensor_type in (SupportedModels.CURTAIN, SupportedModels.CURTAIN_3):
            options[CONF_CURTAIN_SPEED] = DEFAULT_CURTAIN_SPEED
        return MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
                CONF_NAME: "test-name",
                CONF_SENSOR_TYPE: sensor_type,
            },
            unique_id="aabbccddeeff",
            version=2,
            minor_version=1,
            options=options,
        )

    return _create_entry


@pytest.fixture
def mock_entry_encrypted_factory():
    """Create a MockConfigEntry with encryption key and sensor type."""

    def _create_entry(sensor_type: str = "lock") -> MockConfigEntry:
        options: dict[str, int] = {CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT}
        if sensor_type in (SupportedModels.CURTAIN, SupportedModels.CURTAIN_3):
            options[CONF_CURTAIN_SPEED] = DEFAULT_CURTAIN_SPEED
        return MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
                CONF_NAME: "test-name",
                CONF_SENSOR_TYPE: sensor_type,
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
            unique_id="aabbccddeeff",
            version=2,
            minor_version=1,
            options=options,
        )

    return _create_entry
