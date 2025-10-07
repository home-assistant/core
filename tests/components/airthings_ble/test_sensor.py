"""Test the Airthings Wave sensor."""

import logging

import pytest

from homeassistant.components.airthings_ble.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    CO2_V1,
    CO2_V2,
    HUMIDITY_V2,
    TEMPERATURE_V1,
    VOC_V1,
    VOC_V2,
    VOC_V3,
    WAVE_DEVICE_INFO,
    WAVE_ENHANCE_DEVICE_INFO,
    WAVE_ENHANCE_SERVICE_INFO,
    WAVE_SERVICE_INFO,
    create_device,
    create_entry,
    patch_airthings_ble,
    patch_airthings_device_update,
    patch_async_ble_device_from_address,
    patch_async_discovered_service_info,
)

from tests.components.bluetooth import inject_bluetooth_service_info

_LOGGER = logging.getLogger(__name__)


async def test_migration_from_v1_to_v3_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Verify that we can migrate from v1 (pre 2023.9.0) to the latest unique id format."""
    entry = create_entry(hass, WAVE_SERVICE_INFO)
    device = create_device(entry, device_registry, WAVE_SERVICE_INFO, WAVE_DEVICE_INFO)

    assert entry is not None
    assert device is not None

    new_unique_id = f"{WAVE_DEVICE_INFO.address}_temperature"

    sensor = entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform=Platform.SENSOR,
        unique_id=TEMPERATURE_V1.unique_id,
        config_entry=entry,
        device_id=device.id,
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        WAVE_SERVICE_INFO,
    )

    await hass.async_block_till_done()

    with patch_airthings_device_update():
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) > 0

    assert entity_registry.async_get(sensor.entity_id).unique_id == new_unique_id


async def test_migration_from_v2_to_v3_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Verify that we can migrate from v2 (introduced in 2023.9.0) to the latest unique id format."""
    entry = create_entry(hass, WAVE_SERVICE_INFO)
    device = create_device(entry, device_registry, WAVE_SERVICE_INFO, WAVE_DEVICE_INFO)

    assert entry is not None
    assert device is not None

    sensor = entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform=Platform.SENSOR,
        unique_id=HUMIDITY_V2.unique_id,
        config_entry=entry,
        device_id=device.id,
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        WAVE_SERVICE_INFO,
    )

    await hass.async_block_till_done()

    with patch_airthings_device_update():
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) > 0

    # Migration should happen, v2 unique id should be updated to the new format
    new_unique_id = f"{WAVE_DEVICE_INFO.address}_humidity"
    assert entity_registry.async_get(sensor.entity_id).unique_id == new_unique_id


async def test_migration_from_v1_and_v2_to_v3_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test if migration works when we have both v1 (pre 2023.9.0) and v2 (introduced in 2023.9.0) unique ids."""
    entry = create_entry(hass, WAVE_SERVICE_INFO)
    device = create_device(entry, device_registry, WAVE_SERVICE_INFO, WAVE_DEVICE_INFO)

    assert entry is not None
    assert device is not None

    v2 = entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform=Platform.SENSOR,
        unique_id=CO2_V2.unique_id,
        config_entry=entry,
        device_id=device.id,
    )

    v1 = entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform=Platform.SENSOR,
        unique_id=CO2_V1.unique_id,
        config_entry=entry,
        device_id=device.id,
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        WAVE_SERVICE_INFO,
    )

    await hass.async_block_till_done()

    with patch_airthings_device_update():
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) > 0

    # Migration should happen, v1 unique id should be updated to the new format
    new_unique_id = f"{WAVE_DEVICE_INFO.address}_co2"
    assert entity_registry.async_get(v1.entity_id).unique_id == new_unique_id
    assert entity_registry.async_get(v2.entity_id).unique_id == CO2_V2.unique_id


async def test_migration_with_all_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test if migration works when we have all unique ids."""
    entry = create_entry(hass, WAVE_SERVICE_INFO)
    device = create_device(entry, device_registry, WAVE_SERVICE_INFO, WAVE_DEVICE_INFO)

    assert entry is not None
    assert device is not None

    v1 = entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform=Platform.SENSOR,
        unique_id=VOC_V1.unique_id,
        config_entry=entry,
        device_id=device.id,
    )

    v2 = entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform=Platform.SENSOR,
        unique_id=VOC_V2.unique_id,
        config_entry=entry,
        device_id=device.id,
    )

    v3 = entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform=Platform.SENSOR,
        unique_id=VOC_V3.unique_id,
        config_entry=entry,
        device_id=device.id,
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        WAVE_SERVICE_INFO,
    )

    await hass.async_block_till_done()

    with patch_airthings_device_update():
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) > 0

    # No migration should happen, unique id should be the same as before
    assert entity_registry.async_get(v1.entity_id).unique_id == VOC_V1.unique_id
    assert entity_registry.async_get(v2.entity_id).unique_id == VOC_V2.unique_id
    assert entity_registry.async_get(v3.entity_id).unique_id == VOC_V3.unique_id


@pytest.mark.parametrize(
    ("unique_suffix", "expected_sensor_name"),
    [
        ("lux", "Illuminance"),
        ("noise", "Ambient noise"),
    ],
)
async def test_translation_keys(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    unique_suffix: str,
    expected_sensor_name: str,
) -> None:
    """Test that translated sensor names are correct."""
    entry = create_entry(hass, WAVE_ENHANCE_SERVICE_INFO)
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
