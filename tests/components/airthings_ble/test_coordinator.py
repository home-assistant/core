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

from . import CORENTIUM_HOME_2_DEVICE_INFO, WAVE_DEVICE_INFO, WAVE_ENHANCE_DEVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_ble_device


@pytest.mark.parametrize(
    ("device_info", "expected_interval"),
    [
        (CORENTIUM_HOME_2_DEVICE_INFO, RADON_SCAN_INTERVAL),
        (WAVE_DEVICE_INFO, DEFAULT_SCAN_INTERVAL),
        (WAVE_ENHANCE_DEVICE_INFO, DEFAULT_SCAN_INTERVAL),
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
            data={"device_model": device_info.model.value},
        ),
    )
    coordinator.ble_device = generate_ble_device("cc:cc:cc:cc:cc:cc", device_info.name)

    assert coordinator.update_interval == timedelta(seconds=expected_interval)


async def test_migration_existing_entry(
    hass: HomeAssistant,
) -> None:
    """Test migration of existing config entry without device_model."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="cc:cc:cc:cc:cc:cc",
        data={},
    )
    entry.add_to_hass(hass)

    coordinator = AirthingsBLEDataUpdateCoordinator(
        hass=hass,
        entry=entry,
    )
    coordinator.ble_device = generate_ble_device(
        "cc:cc:cc:cc:cc:cc", CORENTIUM_HOME_2_DEVICE_INFO.name
    )

    assert coordinator.update_interval == timedelta(seconds=DEFAULT_SCAN_INTERVAL)
    assert "device_model" not in entry.data

    with patch(
        "homeassistant.components.airthings_ble.coordinator.AirthingsBluetoothDeviceData.update_device",
        return_value=CORENTIUM_HOME_2_DEVICE_INFO,
    ):
        await coordinator.async_refresh()

    assert "device_model" in entry.data
    assert entry.data["device_model"] == CORENTIUM_HOME_2_DEVICE_INFO.model.value
    assert coordinator.update_interval == timedelta(seconds=RADON_SCAN_INTERVAL)
