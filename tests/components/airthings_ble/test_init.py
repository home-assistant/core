"""Test the Airthings BLE integration init."""

from copy import deepcopy

from airthings_ble import AirthingsDeviceType
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.airthings_ble.const import (
    DEFAULT_SCAN_INTERVAL,
    DEVICE_MODEL,
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

from tests.common import MockConfigEntry, async_fire_time_changed
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

    assert DEVICE_MODEL not in entry.data

    with (
        patch_async_ble_device_from_address(service_info.device),
        patch_airthings_ble(device_info),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Migration should have added device_model to entry data
    assert DEVICE_MODEL in entry.data
    assert entry.data[DEVICE_MODEL] == device_info.model.value


async def test_no_migration_when_device_model_exists(
    hass: HomeAssistant,
) -> None:
    """Test that migration does not run when device_model already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data={DEVICE_MODEL: WAVE_DEVICE_INFO.model.value},
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
    assert entry.data[DEVICE_MODEL] == WAVE_DEVICE_INFO.model.value


async def test_scan_interval_corentium_home_2(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test that coordinator uses radon scan interval for Corentium Home 2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data={DEVICE_MODEL: CORENTIUM_HOME_2_DEVICE_INFO.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WAVE_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(WAVE_SERVICE_INFO.device),
        patch_airthings_ble(CORENTIUM_HOME_2_DEVICE_INFO),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert (
            hass.states.get("sensor.airthings_corentium_home_2_123456_battery").state
            == "90"
        )

    changed_info = deepcopy(CORENTIUM_HOME_2_DEVICE_INFO)
    changed_info.sensors["battery"] = 89

    with patch_airthings_ble(changed_info):
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert (
            hass.states.get("sensor.airthings_corentium_home_2_123456_battery").state
            == "90"
        )

        freezer.tick(
            DEVICE_SPECIFIC_SCAN_INTERVAL.get(
                AirthingsDeviceType.CORENTIUM_HOME_2.value
            )
            - DEFAULT_SCAN_INTERVAL
        )
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert (
            hass.states.get("sensor.airthings_corentium_home_2_123456_battery").state
            == "89"
        )


@pytest.mark.parametrize(
    ("service_info", "device_info", "battery_entity_id"),
    [
        (WAVE_SERVICE_INFO, WAVE_DEVICE_INFO, "sensor.airthings_wave_123456_battery"),
        (
            WAVE_ENHANCE_SERVICE_INFO,
            WAVE_ENHANCE_DEVICE_INFO,
            "sensor.airthings_wave_enhance_123456_battery",
        ),
    ],
)
async def test_coordinator_default_scan_interval(
    hass: HomeAssistant,
    service_info,
    device_info,
    freezer: FrozenDateTimeFactory,
    battery_entity_id: str,
) -> None:
    """Test that coordinator uses default scan interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=service_info.address,
        data={DEVICE_MODEL: device_info.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, service_info)

    with (
        patch_async_ble_device_from_address(service_info.device),
        patch_airthings_ble(device_info),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get(battery_entity_id).state == "85"

    changed_info = deepcopy(device_info)
    changed_info.sensors["battery"] = 84

    with patch_airthings_ble(changed_info):
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert hass.states.get(battery_entity_id).state == "84"
