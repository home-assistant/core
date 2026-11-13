"""Services for the Rachio integration."""

import logging

import probatio

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ID, CommonServiceArgument, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    service,
)
from homeassistant.helpers.service import async_register_platform_entity_service

from .const import (
    DOMAIN,
    KEY_ID,
    MODEL_GENERATION_1,
    RachioService,
    RachioServiceArgument,
)
from .device import RachioConfigEntry

_LOGGER = logging.getLogger(__name__)

ATTR_DURATION = "duration"
ATTR_SORT_ORDER = "sortOrder"

PAUSE_SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Optional(RachioServiceArgument.DEVICES): cv.string,
        probatio.Optional(RachioServiceArgument.DURATION, default=60): cv.positive_int,
    }
)

RESUME_SERVICE_SCHEMA = probatio.Schema(
    {probatio.Optional(RachioServiceArgument.DEVICES): cv.string}
)

START_MULTIPLE_ZONES_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.ENTITY_ID): cv.entity_ids,
        probatio.Required(RachioServiceArgument.DURATION): cv.ensure_list_csv,
    }
)

STOP_SERVICE_SCHEMA = probatio.Schema(
    {probatio.Optional(RachioServiceArgument.DEVICES): cv.string}
)


def _stop_water(call: ServiceCall) -> None:
    """Stop watering on all or specific controllers."""
    entry: RachioConfigEntry = service.async_get_config_entry(call.hass, DOMAIN, None)
    person = entry.runtime_data
    devices = call.data.get(
        RachioServiceArgument.DEVICES, [iro.name for iro in person.controllers]
    )
    for iro in person.controllers:
        if iro.name in devices:
            iro.stop_watering()


def _pause_water(call: ServiceCall) -> None:
    """Pause watering on all or specific controllers."""
    entry: RachioConfigEntry = service.async_get_config_entry(call.hass, DOMAIN, None)
    person = entry.runtime_data
    devices = call.data.get(
        RachioServiceArgument.DEVICES, [iro.name for iro in person.controllers]
    )
    for iro in person.controllers:
        if iro.name in devices and iro.model.split("_")[0] != MODEL_GENERATION_1:
            iro.pause_watering(call.data[RachioServiceArgument.DURATION])


def _resume_water(call: ServiceCall) -> None:
    """Resume watering on all or specific controllers."""
    entry: RachioConfigEntry = service.async_get_config_entry(call.hass, DOMAIN, None)
    person = entry.runtime_data
    devices = call.data.get(
        RachioServiceArgument.DEVICES, [iro.name for iro in person.controllers]
    )
    for iro in person.controllers:
        if iro.name in devices and iro.model.split("_")[0] != MODEL_GENERATION_1:
            iro.resume_watering()


def _start_multiple(call: ServiceCall) -> None:
    """Start multiple zones in sequence."""
    entry: RachioConfigEntry = service.async_get_config_entry(call.hass, DOMAIN, None)
    person = entry.runtime_data
    entity_reg = er.async_get(call.hass)
    duration = iter(call.data[RachioServiceArgument.DURATION])
    default_time = call.data[RachioServiceArgument.DURATION][0]

    entity_to_zone_id = {
        entity_reg.async_get_entity_id(
            Platform.SWITCH,
            DOMAIN,
            f"{controller.controller_id}-zone-{zone[KEY_ID]}",
        ): zone[KEY_ID]
        for controller in person.controllers
        for zone in controller.list_zones()
    }

    zones_list = [
        {
            ATTR_ID: entity_to_zone_id[entity_id],
            ATTR_DURATION: int(next(duration, default_time)) * 60,
            ATTR_SORT_ORDER: count,
        }
        for count, entity_id in enumerate(call.data[CommonServiceArgument.ENTITY_ID])
        if entity_id in entity_to_zone_id
    ]

    if not zones_list:
        raise HomeAssistantError("No matching zones found in given entity_ids")

    person.start_multiple_zones(zones_list)
    _LOGGER.debug("Starting zone(s) %s", call.data[CommonServiceArgument.ENTITY_ID])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Rachio services."""

    hass.services.async_register(
        DOMAIN, RachioService.STOP_WATERING, _stop_water, schema=STOP_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, RachioService.PAUSE_WATERING, _pause_water, schema=PAUSE_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        RachioService.RESUME_WATERING,
        _resume_water,
        schema=RESUME_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        RachioService.START_MULTIPLE_ZONE_SCHEDULE,
        _start_multiple,
        schema=START_MULTIPLE_ZONES_SCHEMA,
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        RachioService.START_WATERING,
        entity_domain=SWITCH_DOMAIN,
        func="turn_on",
        schema={probatio.Optional(RachioServiceArgument.DURATION): cv.positive_int},
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        RachioService.SET_ZONE_MOISTURE_PERCENT,
        entity_domain=SWITCH_DOMAIN,
        func="set_moisture_percent",
        schema={probatio.Required(RachioServiceArgument.PERCENT): cv.positive_int},
    )
