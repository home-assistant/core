"""Test the Airthings BLE integration init."""

from homeassistant.components.airthings_ble.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import (
    CORENTIUM_HOME_2_DEVICE_INFO,
    WAVE_DEVICE_INFO,
    WAVE_SERVICE_INFO,
    patch_airthings_ble,
    patch_async_ble_device_from_address,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_migration_existing_entry_radon_device(
    hass: HomeAssistant,
) -> None:
    """Test migration of existing config entry without device_model for radon device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data={},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WAVE_SERVICE_INFO)

    assert "device_model" not in entry.data

    with (
        patch_async_ble_device_from_address(WAVE_SERVICE_INFO.device),
        patch_airthings_ble(CORENTIUM_HOME_2_DEVICE_INFO),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Migration should have added device_model to entry data
    assert "device_model" in entry.data
    assert entry.data["device_model"] == CORENTIUM_HOME_2_DEVICE_INFO.model.value


async def test_migration_existing_entry_non_radon_device(
    hass: HomeAssistant,
) -> None:
    """Test migration of existing config entry without device_model for non-radon device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data={},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WAVE_SERVICE_INFO)

    assert "device_model" not in entry.data

    with (
        patch_async_ble_device_from_address(WAVE_SERVICE_INFO.device),
        patch_airthings_ble(WAVE_DEVICE_INFO),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Migration should have added device_model to entry data
    assert "device_model" in entry.data
    assert entry.data["device_model"] == WAVE_DEVICE_INFO.model.value


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
