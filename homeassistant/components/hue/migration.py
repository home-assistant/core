"""Various helpers to handle config entry and api schema migrations."""

import logging

from aiohue import HueBridgeV2
from aiohue.discovery import is_v2_bridge
from aiohue.v2.models.resource import ResourceTypes

from homeassistant import core
from homeassistant.components.binary_sensor import DEVICE_CLASS_MOTION
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_USERNAME,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
)
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry as entities_for_config_entry,
    async_entries_for_device,
    async_get as async_get_entity_registry,
)

from .const import CONF_API_VERSION, DOMAIN

LOGGER = logging.getLogger(__name__)


async def check_migration(hass: core.HomeAssistant, entry: ConfigEntry) -> None:
    """Check if config entry needs any migration actions."""
    host = entry.data[CONF_HOST]

    # migrate CONF_USERNAME --> CONF_API_KEY
    if CONF_USERNAME in entry.data:
        LOGGER.info("Migrate %s to %s in schema", CONF_USERNAME, CONF_API_KEY)
        data = dict(entry.data)
        data[CONF_API_KEY] = data.pop(CONF_USERNAME)
        hass.config_entries.async_update_entry(entry, data=data)

    conf_api_version = entry.data.get(CONF_API_VERSION, 1)
    if conf_api_version == 1:
        # a bridge might have upgraded firmware since last run so
        # we discover its capabilities at every startup
        websession = aiohttp_client.async_get_clientsession(hass)
        if await is_v2_bridge(host, websession):
            supported_api_version = 2
        else:
            supported_api_version = 1
        LOGGER.debug(
            "Configured api version is %s and supported api version %s for bridge %s",
            conf_api_version,
            supported_api_version,
            host,
        )

        # the call to `is_v2_bridge` returns (silently) False even on connection error
        # so if a migration is needed it will be done on next startup

        if conf_api_version == 1 and supported_api_version == 2:
            # run entity/device schema migration for v2
            await handle_v2_migration(hass, entry)

        # store api version in entry data
        if (
            CONF_API_VERSION not in entry.data
            or conf_api_version != supported_api_version
        ):
            data = dict(entry.data)
            data[CONF_API_VERSION] = supported_api_version
            hass.config_entries.async_update_entry(entry, data=data)


async def handle_v2_migration(hass: core.HomeAssistant, entry: ConfigEntry) -> None:
    """Perform migration of devices and entities to V2 Id's."""
    host = entry.data[CONF_HOST]
    api_key = entry.data[CONF_API_KEY]
    websession = aiohttp_client.async_get_clientsession(hass)
    dev_reg = async_get_device_registry(hass)
    ent_reg = async_get_entity_registry(hass)
    LOGGER.info("Start of migration of devices and entities to support API schema 2")
    # initialize bridge connection just for the migration
    async with HueBridgeV2(host, api_key, websession) as api:

        sensor_class_mapping = {
            DEVICE_CLASS_BATTERY: ResourceTypes.DEVICE_POWER,
            DEVICE_CLASS_MOTION: ResourceTypes.MOTION,
            DEVICE_CLASS_ILLUMINANCE: ResourceTypes.LIGHT_LEVEL,
            DEVICE_CLASS_TEMPERATURE: ResourceTypes.TEMPERATURE,
        }

        # handle entities attached to device
        for hue_dev in api.devices:
            zigbee = api.devices.get_zigbee_connectivity(hue_dev.id)
            if not zigbee:
                # not a zigbee device
                continue
            mac = zigbee.mac_address
            # get/update existing device by V1 identifier (mac address)
            # the device will now have both the old and the new identifier
            identifiers = {(DOMAIN, hue_dev.id), (DOMAIN, mac)}
            hass_dev = dev_reg.async_get_or_create(
                config_entry_id=entry.entry_id, identifiers=identifiers
            )
            LOGGER.info("Migrated device %s (%s)", hass_dev.name, hass_dev.id)
            # loop through al entities for device and find match
            for ent in async_entries_for_device(ent_reg, hass_dev.id, True):
                # migrate light
                if ent.entity_id.startswith("light"):
                    # should always return one lightid here
                    new_unique_id = next(iter(hue_dev.lights))
                    if ent.unique_id == new_unique_id:
                        continue  # just in case
                    LOGGER.info(
                        "Migrating %s from unique id %s to %s",
                        ent.entity_id,
                        ent.unique_id,
                        new_unique_id,
                    )
                    ent_reg.async_update_entity(
                        ent.entity_id, new_unique_id=new_unique_id
                    )
                    continue
                # migrate sensors
                matched_dev_class = sensor_class_mapping.get(
                    ent.original_device_class or "unknown"
                )
                if matched_dev_class is None:
                    # this may happen if we're looking at orphaned or unsupported entity
                    LOGGER.warning(
                        "Skip migration of %s because it no longer exists on the bridge",
                        ent.entity_id,
                    )
                    continue
                for sensor in api.devices.get_sensors(hue_dev.id):
                    if sensor.type != matched_dev_class:
                        continue
                    new_unique_id = sensor.id
                    if ent.unique_id == new_unique_id:
                        break  # just in case
                    LOGGER.info(
                        "Migrating %s from unique id %s to %s",
                        ent.entity_id,
                        ent.unique_id,
                        new_unique_id,
                    )
                    try:
                        ent_reg.async_update_entity(
                            ent.entity_id, new_unique_id=sensor.id
                        )
                    except ValueError:
                        # assume edge case where the entity was already migrated in a previous run
                        # which got aborted somehow and we do not want
                        # to crash the entire integration init
                        LOGGER.warning(
                            "Skip migration of %s because it already exists",
                            ent.entity_id,
                        )
                    break

        # migrate entities that are not connected to a device (groups)
        for ent in entities_for_config_entry(ent_reg, entry.entry_id):
            if ent.device_id is not None:
                continue
            v1_id = f"/groups/{ent.unique_id}"
            hue_group = api.groups.room.get_by_v1_id(v1_id)
            if hue_group is None or hue_group.grouped_light is None:
                # this may happen if we're looking at some orphaned entity
                LOGGER.warning(
                    "Skip migration of %s because it no longer exist on the bridge",
                    ent.entity_id,
                )
                continue
            new_unique_id = hue_group.grouped_light
            LOGGER.info(
                "Migrating %s from unique id %s to %s ",
                ent.entity_id,
                ent.unique_id,
                new_unique_id,
            )
            try:
                ent_reg.async_update_entity(ent.entity_id, new_unique_id=new_unique_id)
            except ValueError:
                # assume edge case where the entity was already migrated in a previous run
                # which got aborted somehow and we do not want
                # to crash the entire integration init
                LOGGER.warning(
                    "Skip migration of %s because it already exists",
                    ent.entity_id,
                )
    LOGGER.info("Migration of devices and entities to support API schema 2 finished")
