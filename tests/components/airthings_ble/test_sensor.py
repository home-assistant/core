"""Test the Airthings Wave sensor."""

from copy import deepcopy
from datetime import timedelta
import logging
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.airthings_ble.const import (
    DEFAULT_SCAN_INTERVAL,
    DEVICE_MODEL,
    DEVICE_SPECIFIC_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    CORENTIUM_HOME_2_DEVICE_INFO,
    CORENTIUM_HOME_2_SERVICE_INFO,
    WAVE_DEVICE_INFO,
    WAVE_ENHANCE_DEVICE_INFO,
    WAVE_ENHANCE_SERVICE_INFO,
    WAVE_SERVICE_INFO,
    AirthingsDevice,
    BluetoothServiceInfoBleak,
    create_device,
    create_entry,
    patch_airthings_ble,
    patch_async_ble_device_from_address,
    patch_async_discovered_service_info,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import inject_bluetooth_service_info

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    ("unique_suffix", "expected_sensor_name"),
    [
        ("lux", "Illuminance"),
        ("noise", "Ambient noise"),
    ],
)
async def test_translation_keys_wave_enhance(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    unique_suffix: str,
    expected_sensor_name: str,
) -> None:
    """Test that translated sensor names are correct."""
    entry = create_entry(hass, WAVE_ENHANCE_SERVICE_INFO, WAVE_ENHANCE_DEVICE_INFO)
    device = create_device(
        entry, device_registry, WAVE_ENHANCE_SERVICE_INFO, WAVE_ENHANCE_DEVICE_INFO
    )

    with (
        patch_async_ble_device_from_address(WAVE_ENHANCE_SERVICE_INFO.device),
        patch_async_discovered_service_info([WAVE_ENHANCE_SERVICE_INFO]),
        patch_airthings_ble(WAVE_ENHANCE_DEVICE_INFO),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert device is not None
    assert device.name == "Airthings Wave Enhance (123456)"

    unique_id = f"{WAVE_ENHANCE_DEVICE_INFO.address}_{unique_suffix}"
    entity_id = entity_registry.async_get_entity_id(Platform.SENSOR, DOMAIN, unique_id)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None

    expected_value = WAVE_ENHANCE_DEVICE_INFO.sensors[unique_suffix]
    assert state.state == str(expected_value)

    expected_name = f"Airthings Wave Enhance (123456) {expected_sensor_name}"
    assert state.attributes.get("friendly_name") == expected_name


async def test_disabled_connectivity_mode_corentium_home_2(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that translated sensor names are correct for disabled sensors."""
    entry = create_entry(
        hass,
        CORENTIUM_HOME_2_SERVICE_INFO,
        CORENTIUM_HOME_2_DEVICE_INFO,
    )
    device = create_device(
        entry,
        device_registry,
        CORENTIUM_HOME_2_SERVICE_INFO,
        CORENTIUM_HOME_2_DEVICE_INFO,
    )

    with (
        patch_async_ble_device_from_address(CORENTIUM_HOME_2_SERVICE_INFO.device),
        patch_async_discovered_service_info([CORENTIUM_HOME_2_SERVICE_INFO]),
        patch_airthings_ble(CORENTIUM_HOME_2_DEVICE_INFO),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert device is not None
    assert device.name == "Airthings Corentium Home 2 (123456)"

    unique_id = f"{CORENTIUM_HOME_2_DEVICE_INFO.address}_connectivity_mode"

    entity_id = entity_registry.async_get_entity_id(Platform.SENSOR, DOMAIN, unique_id)
    assert entity_id is not None

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("source_value", "expected_state"),
    [
        (None, STATE_UNKNOWN),
        (123, STATE_UNKNOWN),
        (45.6, STATE_UNKNOWN),
        ("Bluetooth", "bluetooth"),
    ],
)
async def test_connectivity_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    source_value: Any,
    expected_state: str,
) -> None:
    """Test that non-string connectivity mode values are handled correctly."""
    test_device = deepcopy(CORENTIUM_HOME_2_DEVICE_INFO)

    # Non-string value, will be mapped to 'unknown' state
    test_device.sensors["connectivity_mode"] = source_value

    entry = create_entry(hass, CORENTIUM_HOME_2_SERVICE_INFO, test_device)
    create_device(entry, device_registry, CORENTIUM_HOME_2_SERVICE_INFO, test_device)

    with (
        patch_async_ble_device_from_address(CORENTIUM_HOME_2_SERVICE_INFO.device),
        patch_async_discovered_service_info([CORENTIUM_HOME_2_SERVICE_INFO]),
        patch_airthings_ble(test_device),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(
        "sensor.airthings_corentium_home_2_123456_connectivity_mode"
    )
    assert state is not None
    assert state.state == expected_state


async def test_scan_interval_migration_corentium_home_2(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that radon device migration uses 30-minute scan interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data={},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WAVE_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(WAVE_SERVICE_INFO.device),
        patch_airthings_ble(CORENTIUM_HOME_2_DEVICE_INFO) as mock_update,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Migration should have added device_model to entry data
        assert DEVICE_MODEL in entry.data
        assert entry.data[DEVICE_MODEL] == CORENTIUM_HOME_2_DEVICE_INFO.model.value

        # Coordinator should have been configured with radon scan interval
        coordinator = entry.runtime_data
        assert coordinator.update_interval == timedelta(
            seconds=DEVICE_SPECIFIC_SCAN_INTERVAL.get(
                CORENTIUM_HOME_2_DEVICE_INFO.model.value
            )
        )

        # Should have 2 calls: 1 for migration + 1 for initial refresh
        assert mock_update.call_count == 2

        # Fast forward by default interval (300s) - should NOT trigger update
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_update.call_count == 2

        # Fast forward to radon interval (1800s) - should trigger update
        freezer.tick(
            DEVICE_SPECIFIC_SCAN_INTERVAL.get(CORENTIUM_HOME_2_DEVICE_INFO.model.value)
        )
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_update.call_count == 3


@pytest.mark.parametrize(
    ("service_info", "device_info"),
    [
        (WAVE_SERVICE_INFO, WAVE_DEVICE_INFO),
        (WAVE_ENHANCE_SERVICE_INFO, WAVE_ENHANCE_DEVICE_INFO),
    ],
)
async def test_default_scan_interval_migration(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_info: BluetoothServiceInfoBleak,
    device_info: AirthingsDevice,
) -> None:
    """Test that non-radon device migration uses default 5-minute scan interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=service_info.address,
        data={},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, service_info)

    with (
        patch_async_ble_device_from_address(service_info.device),
        patch_airthings_ble(device_info) as mock_update,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Migration should have added device_model to entry data
        assert DEVICE_MODEL in entry.data
        assert entry.data[DEVICE_MODEL] == device_info.model.value

        # Coordinator should have been configured with default scan interval
        coordinator = entry.runtime_data
        assert coordinator.update_interval == timedelta(seconds=DEFAULT_SCAN_INTERVAL)

        # Should have 2 calls: 1 for migration + 1 for initial refresh
        assert mock_update.call_count == 2

        # Fast forward by default interval (300s) - SHOULD trigger update
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_update.call_count == 3


async def test_device_registry_sw_version_updates_on_refresh(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device firmware version follows a firmware upgrade."""
    first_device = deepcopy(WAVE_DEVICE_INFO)
    second_device = deepcopy(WAVE_DEVICE_INFO)
    first_device.sw_version = "G-BLE-1.5.3-master+0"
    second_device.sw_version = "G-BLE-2.2.3-master+0"

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data={DEVICE_MODEL: first_device.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WAVE_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(WAVE_SERVICE_INFO.device),
        patch_airthings_ble(side_effect=[first_device, second_device]),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device = device_registry.async_get_device_by_connection(
            (dr.CONNECTION_BLUETOOTH, WAVE_DEVICE_INFO.address), entry.entry_id
        )
        assert device is not None
        assert device.sw_version == "G-BLE-1.5.3-master+0"

        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.sw_version == "G-BLE-2.2.3-master+0"
