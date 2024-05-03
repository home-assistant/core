"""Tests for the MicroBot integration."""

from unittest.mock import patch

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

DOMAIN = "keymitt_ble"

ENTRY_CONFIG = {
    CONF_ADDRESS: "e7:89:43:99:99:99",
}

USER_INPUT = {
    CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
}

USER_INPUT_INVALID = {
    CONF_ADDRESS: "invalid-mac",
}


def patch_async_setup_entry(return_value=True):
    """Patch async setup entry to return True."""
    return patch(
        "homeassistant.components.keymitt_ble.async_setup_entry",
        return_value=return_value,
    )


SERVICE_INFO = BluetoothServiceInfoBleak(
    name="mibp",
    service_uuids=["0000abcd-0000-1000-8000-00805f9b34fb"],
    address="aa:bb:cc:dd:ee:ff",
    manufacturer_data={},
    service_data={},
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="mibp",
        manufacturer_data={},
        service_uuids=["0000abcd-0000-1000-8000-00805f9b34fb"],
    ),
    device=generate_ble_device("aa:bb:cc:dd:ee:ff", "mibp"),
    time=0,
    connectable=True,
    tx_power=-127,
)


class MockMicroBotApiClient:
    """Mock MicroBotApiClient."""

    def __init__(self, device, token):
        """Mock init."""

    async def connect(self, init):
        """Mock connect."""

    async def disconnect(self):
        """Mock disconnect."""

    def is_connected(self):
        """Mock connected."""
        return True


class MockMicroBotApiClientFail:
    """Mock MicroBotApiClient."""

    def __init__(self, device, token):
        """Mock init."""

    async def connect(self, init):
        """Mock connect."""

    async def disconnect(self):
        """Mock disconnect."""

    async def is_connected(self):
        """Mock disconnected."""
        return False
