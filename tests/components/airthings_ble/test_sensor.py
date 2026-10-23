"""Test the Airthings Wave sensor."""

from copy import deepcopy
import logging
from typing import Any

import pytest

from homeassistant.components.airthings_ble.const import DOMAIN
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
    create_device,
    create_entry,
    patch_airthings_ble,
    patch_async_ble_device_from_address,
    patch_async_discovered_service_info,
)

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


async def test_unknown_sensor_type_is_skipped(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that sensor types without a description do not create entities."""
    device_info = deepcopy(WAVE_DEVICE_INFO)
    device_info.sensors = {"unknown_sensor": 42, **WAVE_DEVICE_INFO.sensors}

    entry = create_entry(hass, WAVE_SERVICE_INFO, device_info)

    with (
        patch_async_ble_device_from_address(WAVE_SERVICE_INFO.device),
        patch_airthings_ble(device_info),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert {entity.unique_id for entity in entries} == {
        f"{WAVE_DEVICE_INFO.address}_{sensor}" for sensor in WAVE_DEVICE_INFO.sensors
    }


@pytest.mark.parametrize(
    ("identifier", "expected_device_name"),
    [
        pytest.param("123456", "Airthings Wave+ (123456)", id="identifier"),
        pytest.param("", "Airthings Wave+", id="no_identifier"),
    ],
)
async def test_device_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    identifier: str,
    expected_device_name: str,
) -> None:
    """Test the device name includes the identifier only when one is reported."""
    device_info = deepcopy(WAVE_DEVICE_INFO)
    device_info.identifier = identifier

    entry = create_entry(hass, WAVE_SERVICE_INFO, device_info)

    with (
        patch_async_ble_device_from_address(WAVE_SERVICE_INFO.device),
        patch_airthings_ble(device_info),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_BLUETOOTH, WAVE_DEVICE_INFO.address), entry.entry_id
    )
    assert device is not None
    assert device.name == expected_device_name


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
