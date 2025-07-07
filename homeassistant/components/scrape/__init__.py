"""The scrape component."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import timedelta
import logging
from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant.components.rest import RESOURCE_SCHEMA, create_rest_data_from_config
from homeassistant.components.sensor import CONF_STATE_CLASS, DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery,
    entity_registry as er,
)
from homeassistant.helpers.trigger_template_entity import (
    CONF_AVAILABILITY,
    TEMPLATE_SENSOR_BASE_SCHEMA,
    ValueTemplate,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ENCODING,
    CONF_INDEX,
    CONF_SELECT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import ScrapeCoordinator

type ScrapeConfigEntry = ConfigEntry[ScrapeCoordinator]

_LOGGER = logging.getLogger(__name__)

SENSOR_SCHEMA = vol.Schema(
    {
        **TEMPLATE_SENSOR_BASE_SCHEMA.schema,
        vol.Optional(CONF_AVAILABILITY): cv.template,
        vol.Optional(CONF_ATTRIBUTE): cv.string,
        vol.Optional(CONF_INDEX, default=0): cv.positive_int,
        vol.Required(CONF_SELECT): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): vol.All(
            cv.template, ValueTemplate.from_template
        ),
    }
)

COMBINED_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SCAN_INTERVAL): cv.time_period,
        **RESOURCE_SCHEMA,
        vol.Optional(SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [vol.Schema(SENSOR_SCHEMA)]
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.All(cv.ensure_list, [COMBINED_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Scrape from yaml config."""
    scrape_config: list[ConfigType] | None
    if not (scrape_config := config.get(DOMAIN)):
        return True

    load_coroutines: list[Coroutine[Any, Any, None]] = []
    for resource_config in scrape_config:
        rest = create_rest_data_from_config(hass, resource_config)
        scan_interval: timedelta = resource_config.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        coordinator = ScrapeCoordinator(
            hass, None, rest, resource_config, scan_interval
        )

        sensors: list[ConfigType] = resource_config.get(SENSOR_DOMAIN, [])
        if sensors:
            load_coroutines.append(
                discovery.async_load_platform(
                    hass,
                    Platform.SENSOR,
                    DOMAIN,
                    {"coordinator": coordinator, "configs": sensors},
                    config,
                )
            )

    if load_coroutines:
        await asyncio.gather(*load_coroutines)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ScrapeConfigEntry) -> bool:
    """Set up Scrape from a config entry."""

    config: dict[str, Any] = dict(entry.options)
    config.update(config.pop("advanced", {}))
    config.update(config.pop("auth", {}))

    rest_config: dict[str, Any] = COMBINED_SCHEMA(dict(config))
    rest = create_rest_data_from_config(hass, rest_config)

    coordinator = ScrapeCoordinator(
        hass,
        entry,
        rest,
        rest_config,
        DEFAULT_SCAN_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ScrapeConfigEntry) -> bool:
    """Migrate old entry."""

    if entry.version > 2:
        # Don't migrate from future version
        return False

    if entry.version == 1:
        old_to_new_sensor_id = {}
        for sensor in entry.options[SENSOR_DOMAIN]:
            # Create a new sub config entry per sensor
            sensor_config = dict(sensor)
            title = sensor_config.pop(CONF_NAME)
            old_unique_id = sensor_config.pop(CONF_UNIQUE_ID)

            sensor_config["advanced"] = {}
            for sensor_advanced_key in (
                CONF_ATTRIBUTE,
                CONF_VALUE_TEMPLATE,
                CONF_AVAILABILITY,
                CONF_DEVICE_CLASS,
                CONF_STATE_CLASS,
                CONF_UNIT_OF_MEASUREMENT,
            ):
                if sensor_advanced_key in sensor_config:
                    sensor_config["advanced"][sensor_advanced_key] = sensor_config.pop(
                        sensor_advanced_key
                    )

            _LOGGER.debug(
                "Migrating sensor %s with unique id %s to sub config entry data %s",
                title,
                old_unique_id,
                sensor_config,
            )
            new_sub_entry = ConfigSubentry(
                data=MappingProxyType(sensor_config),
                subentry_type="entity",
                title=title,
                unique_id=None,
            )
            old_to_new_sensor_id[old_unique_id] = new_sub_entry.subentry_id
            hass.config_entries.async_add_subentry(entry, new_sub_entry)

        # Use the new sub config entry id as the unique id for the sensor entity
        entity_reg = er.async_get(hass)
        entities = er.async_entries_for_config_entry(entity_reg, entry.entry_id)
        for entity in entities:
            if entity.unique_id in old_to_new_sensor_id:
                new_unique_id = old_to_new_sensor_id[old_unique_id]
                _LOGGER.debug(
                    "Migrating entity %s with unique id %s to new unique id %s",
                    entity.entity_id,
                    entity.unique_id,
                    new_unique_id,
                )
                entity_reg.async_update_entity(
                    entity.entity_id,
                    config_entry_id=entry.entry_id,
                    config_subentry_id=new_unique_id,
                    new_unique_id=new_unique_id,
                )

        # Use the new sub config entry id as the unique id for the sensor device
        device_reg = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_reg, entry.entry_id)
        for device in devices:
            for identifier in device.identifiers:
                device_unique_id = identifier[1]
                if device_unique_id in old_to_new_sensor_id:
                    new_unique_id = old_to_new_sensor_id[device_unique_id]
                    _LOGGER.debug(
                        "Migrating device %s with identifiers %s to new unique id %s",
                        device.id,
                        device.identifiers,
                        new_unique_id,
                    )
                    device_reg.async_update_device(
                        device.id,
                        add_config_entry_id=entry.entry_id,
                        add_config_subentry_id=new_unique_id,
                        new_identifiers={(DOMAIN, new_unique_id)},
                    )

        # Remove the sensors as they are now subentries
        new_config_entry_data = dict(entry.options)
        new_config_entry_data.pop(SENSOR_DOMAIN)

        # Update the resource config
        new_config_entry_data["auth"] = {}
        new_config_entry_data["advanced"] = {}
        for resource_advanced_key in (
            CONF_HEADERS,
            CONF_VERIFY_SSL,
            CONF_TIMEOUT,
            CONF_ENCODING,
        ):
            if resource_advanced_key in new_config_entry_data:
                new_config_entry_data["advanced"][resource_advanced_key] = (
                    new_config_entry_data.pop(resource_advanced_key)
                )
        for resource_auth_key in (CONF_AUTHENTICATION, CONF_USERNAME, CONF_PASSWORD):
            if resource_auth_key in new_config_entry_data:
                new_config_entry_data["auth"][resource_auth_key] = (
                    new_config_entry_data.pop(resource_auth_key)
                )

        _LOGGER.debug(
            "Migrating config entry %s from version 1 to version 2 with data %s",
            entry.entry_id,
            new_config_entry_data,
        )
        hass.config_entries.async_update_entry(
            entry, version=2, options=new_config_entry_data
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Scrape config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Remove Scrape config entry from a device."""
    entity_registry = er.async_get(hass)
    for identifier in device.identifiers:
        if identifier[0] == DOMAIN and entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, identifier[1]
        ):
            return False

    return True
