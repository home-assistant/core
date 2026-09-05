"""Fixtures for the Spin EV Charger tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.backends.device import BLEDevice
import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.spinev.const import DOMAIN

from .const import (
    ADDRESS,
    ADVERTISED_NAME,
    ENTRY_DATA,
    ENTRY_OPTIONS,
    SERIAL,
    SERVICE_UUID,
    STATUS,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device


@pytest.fixture
def ble_device() -> BLEDevice:
    """Return the charger as the Bluetooth manager reports it."""
    return generate_ble_device(address=ADDRESS, name=ADVERTISED_NAME)


@pytest.fixture
def service_info(ble_device: BLEDevice) -> BluetoothServiceInfoBleak:
    """Return a discovery payload for the charger."""
    return BluetoothServiceInfoBleak(
        name=ADVERTISED_NAME,
        address=ADDRESS,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[SERVICE_UUID],
        source="local",
        device=ble_device,
        advertisement=generate_advertisement_data(
            local_name=ADVERTISED_NAME,
            manufacturer_data={},
            service_data={},
            service_uuids=[SERVICE_UUID],
        ),
        connectable=True,
        time=0,
        tx_power=-127,
    )


@pytest.fixture
def mock_charger() -> Generator[AsyncMock]:
    """Patch SpinEvCharger everywhere it is constructed."""
    charger = AsyncMock()
    charger.async_get_status.return_value = STATUS
    charger.async_get_state_value.return_value = 4
    charger.__aenter__.return_value = charger
    charger.is_connected = True

    with (
        patch(
            "homeassistant.components.spinev.coordinator.SpinEvCharger",
            return_value=charger,
        ),
        patch(
            "homeassistant.components.spinev.config_flow.SpinEvCharger",
            return_value=charger,
        ),
    ):
        yield charger


@pytest.fixture(autouse=True)
def mock_ble_device(
    enable_bluetooth: None, ble_device: BLEDevice
) -> Generator[MagicMock]:
    """Make the Bluetooth manager resolve the charger's address."""
    # Both modules import the bluetooth component itself, so one patch of the
    # lookup covers the coordinator and the config flow alike.
    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=ble_device,
        ) as mock_lookup,
        patch(
            "homeassistant.components.spinev.coordinator.close_stale_connections_by_address"
        ),
        patch(
            "homeassistant.components.bluetooth.async_address_reachability_diagnostics",
            return_value="No Bluetooth adapter or proxy is in range of it.",
        ),
        patch(
            "homeassistant.components.bluetooth.async_request_active_scan",
            new_callable=AsyncMock,
        ),
    ):
        yield mock_lookup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for the charger."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=SERIAL,
        unique_id=ADDRESS,
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Stop the entry a flow creates from setting the integration up."""
    with patch(
        "homeassistant.components.spinev.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
