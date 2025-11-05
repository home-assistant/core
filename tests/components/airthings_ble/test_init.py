"""Test the Airthings BLE integration init."""

from datetime import timedelta

import pytest

from homeassistant.components.airthings_ble.const import (
    DEFAULT_SCAN_INTERVAL,
    DEVICE_SPECIFIC_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from . import (
    CORENTIUM_HOME_2_DEVICE_INFO,
    CORENTIUM_HOME_2_SERVICE_INFO,
    WAVE_DEVICE_INFO,
    WAVE_ENHANCE_DEVICE_INFO,
    WAVE_ENHANCE_SERVICE_INFO,
    WAVE_SERVICE_INFO,
    patch_airthings_ble,
    patch_async_ble_device_from_address,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    ("service_info", "device_info"),
    [
        (WAVE_SERVICE_INFO, WAVE_DEVICE_INFO),
        (WAVE_ENHANCE_SERVICE_INFO, WAVE_ENHANCE_DEVICE_INFO),
        (CORENTIUM_HOME_2_SERVICE_INFO, CORENTIUM_HOME_2_DEVICE_INFO),
    ],
)
async def test_migration_existing_entries(
    hass: HomeAssistant,
    service_info,
    device_info,
) -> None:
    """Test migration of existing config entry without device model."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=service_info.address,
        data={},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, service_info)

    assert "device_model" not in entry.data

    with (
        patch_async_ble_device_from_address(service_info.device),
        patch_airthings_ble(device_info),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Migration should have added device_model to entry data
    assert "device_model" in entry.data
    assert entry.data["device_model"] == device_info.model.value


async def test_no_migration_when_device_model_exists(
    hass: HomeAssistant,
) -> None:
    """Test that migration does not run when device_model already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data={"device_model": WAVE_DEVICE_INFO.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WAVE_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(WAVE_SERVICE_INFO.device),
        patch_airthings_ble(WAVE_DEVICE_INFO) as mock_update,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Should have only 1 call for initial refresh (no migration call)
    assert mock_update.call_count == 1
    assert entry.data["device_model"] == WAVE_DEVICE_INFO.model.value


async def test_scan_interval_corentium_home_2(
    hass: HomeAssistant,
) -> None:
    """Test that coordinator uses radon scan interval for Corentium Home 2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data={"device_model": CORENTIUM_HOME_2_DEVICE_INFO.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WAVE_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(WAVE_SERVICE_INFO.device),
        patch_airthings_ble(CORENTIUM_HOME_2_DEVICE_INFO),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Coordinator should have radon scan interval
    coordinator = entry.runtime_data
    assert coordinator.update_interval == timedelta(
        seconds=DEVICE_SPECIFIC_SCAN_INTERVAL.get(
            CORENTIUM_HOME_2_DEVICE_INFO.model.value, DEFAULT_SCAN_INTERVAL
        )
    )


@pytest.mark.parametrize(
    ("service_info", "device_info"),
    [
        (WAVE_SERVICE_INFO, WAVE_DEVICE_INFO),
        (WAVE_ENHANCE_SERVICE_INFO, WAVE_ENHANCE_DEVICE_INFO),
    ],
)
async def test_coordinator_default_scan_interval(
    hass: HomeAssistant,
    service_info,
    device_info,
) -> None:
    """Test that coordinator uses default scan interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=service_info.address,
        data={"device_model": device_info.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, service_info)

    with (
        patch_async_ble_device_from_address(service_info.device),
        patch_airthings_ble(device_info),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Coordinator should have default scan interval
    coordinator = entry.runtime_data
    assert coordinator.update_interval == timedelta(seconds=DEFAULT_SCAN_INTERVAL)
