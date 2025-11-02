"""Test the Airthings BLE coordinator."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.airthings_ble.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    RADON_SCAN_INTERVAL,
)
from homeassistant.components.airthings_ble.coordinator import (
    AirthingsBLEDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant

from . import CORENTIUM_HOME_2_DEVICE_INFO, WAVE_DEVICE_INFO

from tests.components.bluetooth import MockConfigEntry, generate_ble_device


@pytest.mark.parametrize(
    ("device_info", "expected_interval"),
    [
        (CORENTIUM_HOME_2_DEVICE_INFO, RADON_SCAN_INTERVAL),
        (WAVE_DEVICE_INFO, DEFAULT_SCAN_INTERVAL),
    ],
)
async def test_scan_interval_adjustment(
    hass: HomeAssistant,
    device_info,
    expected_interval: int,
) -> None:
    """Test that scan interval is adjusted based on device type."""
    coordinator = AirthingsBLEDataUpdateCoordinator(
        hass=hass,
        entry=MockConfigEntry(
            domain=DOMAIN,
            unique_id="cc:cc:cc:cc:cc:cc",
        ),
    )
    coordinator.ble_device = generate_ble_device("cc:cc:cc:cc:cc:cc", device_info.name)

    assert coordinator.update_interval == timedelta(seconds=DEFAULT_SCAN_INTERVAL)

    with patch(
        "homeassistant.components.airthings_ble.coordinator.AirthingsBluetoothDeviceData.update_device",
        return_value=device_info,
    ):
        await coordinator.async_refresh()

    assert coordinator.update_interval == timedelta(seconds=expected_interval)
