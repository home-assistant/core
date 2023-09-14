"""Test the Airthings Wave sensor."""
import logging

from homeassistant.components.airthings_ble.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.components.airthings_ble import (
    CO2_V1,
    CO2_V2,
    HUMIDITY_V2,
    TEMPERATURE_V1,
    VOC_V1,
    VOC_V2,
    VOC_V3,
    WAVE_DEVICE_INFO,
    WAVE_SERVICE_INFO,
    create_device,
    create_entry,
    patch_airthings_device_update,
)
from tests.components.bluetooth import inject_bluetooth_service_info

_LOGGER = logging.getLogger(__name__)


async def test_migration_from_v1_to_v3_unique_id(hass: HomeAssistant):
    """Verify that we can migrate from v1 (pre 2023.9.0) to the latest unique id format."""
    entry = create_entry(hass)
    device = create_device(hass, entry)

    assert entry is not None
    assert device is not None

    new_unique_id = f"{WAVE_DEVICE_INFO.address}_temperature"

    entity_registry = hass.helpers.entity_registry.async_get(hass)

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


async def test_migration_from_v2_to_v3_unique_id(hass: HomeAssistant):
    """Verify that we can migrate from v2 (introduced in 2023.9.0) to the latest unique id format."""
    entry = create_entry(hass)
    device = create_device(hass, entry)

    assert entry is not None
    assert device is not None

    new_unique_id = f"{WAVE_DEVICE_INFO.address}_humidity"

    entity_registry = hass.helpers.entity_registry.async_get(hass)

    await hass.async_block_till_done()

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

    assert entity_registry.async_get(sensor.entity_id).unique_id == new_unique_id


async def test_migration_from_v1_and_v2_to_v3_unique_id(hass: HomeAssistant):
    """Test if migration works when we have both v1 (pre 2023.9.0) and v2 (introduced in 2023.9.0) unique ids."""
    entry = create_entry(hass)
    device = create_device(hass, entry)

    assert entry is not None
    assert device is not None

    new_unique_id = f"{WAVE_DEVICE_INFO.address}_co2"

    entity_registry = hass.helpers.entity_registry.async_get(hass)

    await hass.async_block_till_done()

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

    assert entity_registry.async_get(v1.entity_id).unique_id == new_unique_id
    assert entity_registry.async_get(v2.entity_id).unique_id == CO2_V2.unique_id


async def test_migration_with_all_unique_ids(hass: HomeAssistant):
    """Test if migration works when we have all unique ids."""
    entry = create_entry(hass)
    device = create_device(hass, entry)

    assert entry is not None
    assert device is not None

    entity_registry = hass.helpers.entity_registry.async_get(hass)

    await hass.async_block_till_done()

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

    assert entity_registry.async_get(v1.entity_id).unique_id == VOC_V1.unique_id
    assert entity_registry.async_get(v2.entity_id).unique_id == VOC_V2.unique_id
    assert entity_registry.async_get(v3.entity_id).unique_id == VOC_V3.unique_id
