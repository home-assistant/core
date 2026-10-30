"""Services for the WiLight integration."""

from typing import Any

import probatio

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import ATTR_PAUSE_TIME, ATTR_WATERING_TIME, DOMAIN
from .support import wilight_trigger as wl_trigger
from .switch import WiLightValvePauseSwitch, WiLightValveSwitch

ATTR_TRIGGER = "trigger"
ATTR_TRIGGER_INDEX = "trigger_index"

SERVICE_SET_WATERING_TIME = "set_watering_time"
SERVICE_SET_PAUSE_TIME = "set_pause_time"
SERVICE_SET_TRIGGER = "set_trigger"

RANGE_WATERING_TIME = 1800
RANGE_PAUSE_TIME = 24
RANGE_TRIGGER_INDEX = 4

VALID_WATERING_TIME = probatio.All(
    probatio.Coerce(int), probatio.Range(min=1, max=RANGE_WATERING_TIME)
)
VALID_PAUSE_TIME = probatio.All(
    probatio.Coerce(int), probatio.Range(min=1, max=RANGE_PAUSE_TIME)
)
VALID_TRIGGER_INDEX = probatio.All(
    probatio.Coerce(int), probatio.Range(min=1, max=RANGE_TRIGGER_INDEX)
)


async def _async_set_watering_time(entity, service_call: Any) -> None:
    if not isinstance(entity, WiLightValveSwitch):
        raise TypeError("Entity is not a WiLight valve switch")
    watering_time = service_call.data[ATTR_WATERING_TIME]
    await entity.async_set_watering_time(watering_time=watering_time)


async def _async_set_trigger(entity, service_call: Any) -> None:
    if not isinstance(entity, WiLightValveSwitch):
        raise TypeError("Entity is not a WiLight valve switch")
    trigger_index = service_call.data[ATTR_TRIGGER_INDEX]
    trigger = service_call.data[ATTR_TRIGGER]
    await entity.async_set_trigger(trigger_index=trigger_index, trigger=trigger)


async def _async_set_pause_time(entity, service_call: Any) -> None:
    if not isinstance(entity, WiLightValvePauseSwitch):
        raise TypeError("Entity is not a WiLight valve pause switch")
    pause_time = service_call.data[ATTR_PAUSE_TIME]
    await entity.async_set_pause_time(pause_time=pause_time)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the WiLight integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_WATERING_TIME,
        entity_domain=SWITCH_DOMAIN,
        schema={
            probatio.Required(ATTR_WATERING_TIME): VALID_WATERING_TIME,
        },
        func=_async_set_watering_time,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_TRIGGER,
        entity_domain=SWITCH_DOMAIN,
        schema={
            probatio.Required(ATTR_TRIGGER_INDEX): VALID_TRIGGER_INDEX,
            probatio.Required(ATTR_TRIGGER): wl_trigger,
        },
        func=_async_set_trigger,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_PAUSE_TIME,
        entity_domain=SWITCH_DOMAIN,
        schema={
            probatio.Required(ATTR_PAUSE_TIME): VALID_PAUSE_TIME,
        },
        func=_async_set_pause_time,
    )
