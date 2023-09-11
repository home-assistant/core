"""Test the Airthings Wave sensor."""
import logging

from homeassistant.components.airthings_ble.const import DOMAIN
from homeassistant.components.airthings_ble.sensor import async_migrate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_entries_for_device

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
)

_LOGGER = logging.getLogger(__name__)


async def test_migration_from_v1_to_v3_unique_id(hass: HomeAssistant):
    """User has a v1 unique id, we should migrate it to v3."""
    entry = create_entry(hass)
    device = create_device(hass, entry)

    assert entry is not None
    assert device is not None

    entity_registry = hass.helpers.entity_registry.async_get(hass)

    await hass.async_block_till_done()

    entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform="sensor",
        unique_id=TEMPERATURE_V1.unique_id,
        config_entry=entry,
        device_id=device.id,
    )

    # Migrate the entities
    async_migrate(hass, WAVE_SERVICE_INFO.address, "temperature")

    entities = async_entries_for_device(
        entity_registry,
        device_id=device.id,
    )

    assert len(entities) == 1
    assert entities[0].unique_id == WAVE_DEVICE_INFO.address + "_temperature"


async def test_migration_from_v2_to_v3_unique_id(hass: HomeAssistant):
    """User has a v2 unique id, we should migrate it to v3."""
    entry = create_entry(hass)
    device = create_device(hass, entry)

    assert entry is not None
    assert device is not None

    entity_registry = hass.helpers.entity_registry.async_get(hass)

    await hass.async_block_till_done()

    entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform="sensor",
        unique_id=HUMIDITY_V2.unique_id,
        config_entry=entry,
        device_id=device.id,
    )

    # Migrate the entities
    async_migrate(hass, WAVE_SERVICE_INFO.address, "humidity")

    entities = async_entries_for_device(
        entity_registry,
        device_id=device.id,
    )

    assert len(entities) == 1
    assert entities[0].unique_id == WAVE_DEVICE_INFO.address + "_humidity"


async def test_migration_from_v1_and_v2_to_v3_unique_id(hass: HomeAssistant):
    """User has a v1 and a v2 unique ids, we should migrate v1 to v3."""
    entry = create_entry(hass)
    device = create_device(hass, entry)

    assert entry is not None
    assert device is not None

    entity_registry = hass.helpers.entity_registry.async_get(hass)

    await hass.async_block_till_done()

    v1 = entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform="sensor",
        unique_id=CO2_V1.unique_id,
        config_entry=entry,
        device_id=device.id,
    )

    v2 = entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform="sensor",
        unique_id=CO2_V2.unique_id,
        config_entry=entry,
        device_id=device.id,
    )

    # Migrate the entities
    async_migrate(hass, WAVE_SERVICE_INFO.address, "co2")

    assert (
        entity_registry.async_get(v1.entity_id).unique_id
        == WAVE_DEVICE_INFO.address + "_co2"
    )
    assert entity_registry.async_get(v2.entity_id).unique_id == v2.unique_id


async def test_migration_with_all_unique_ids(hass: HomeAssistant):
    """User has all unique ids, we should not migrate anything."""
    entry = create_entry(hass)
    device = create_device(hass, entry)

    assert entry is not None
    assert device is not None

    entity_registry = hass.helpers.entity_registry.async_get(hass)

    await hass.async_block_till_done()

    v1 = entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform="sensor",
        unique_id=VOC_V1.unique_id,
        config_entry=entry,
        device_id=device.id,
    )

    v2 = entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform="sensor",
        unique_id=VOC_V2.unique_id,
        config_entry=entry,
        device_id=device.id,
    )

    v3 = entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform="sensor",
        unique_id=VOC_V3.unique_id,
        config_entry=entry,
        device_id=device.id,
    )

    # Migrate the entities
    async_migrate(hass, WAVE_SERVICE_INFO.address, "voc")

    assert entity_registry.async_get(v1.entity_id).unique_id == v1.unique_id
    assert entity_registry.async_get(v2.entity_id).unique_id == v2.unique_id
    assert entity_registry.async_get(v3.entity_id).unique_id == v3.unique_id
