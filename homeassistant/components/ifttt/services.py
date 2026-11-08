"""Services for the IFTTT integration."""

from http import HTTPStatus
import logging

import probatio
import pyfttt
import requests

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    DATA_API_KEYS,
    DATA_IFTTT_ALARM,
    DOMAIN,
    IftttService,
    IftttServiceArgument,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_TRIGGER_SCHEMA = probatio.Schema(
    {
        probatio.Required(IftttServiceArgument.EVENT): cv.string,
        probatio.Optional(IftttServiceArgument.TARGET): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Optional(IftttServiceArgument.VALUE1): cv.string,
        probatio.Optional(IftttServiceArgument.VALUE2): cv.string,
        probatio.Optional(IftttServiceArgument.VALUE3): cv.string,
    }
)

PUSH_ALARM_STATE_SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.ENTITY_ID): cv.entity_ids,
        probatio.Required(IftttServiceArgument.STATE): cv.string,
    }
)


def _trigger_service(call: ServiceCall) -> None:
    """Handle IFTTT trigger service calls."""
    api_keys = call.hass.data.get(DATA_API_KEYS, {})
    event = call.data[IftttServiceArgument.EVENT]
    targets = call.data.get(IftttServiceArgument.TARGET, list(api_keys))
    value1 = call.data.get(IftttServiceArgument.VALUE1)
    value2 = call.data.get(IftttServiceArgument.VALUE2)
    value3 = call.data.get(IftttServiceArgument.VALUE3)

    target_keys = {}
    for target in targets:
        if target not in api_keys:
            _LOGGER.error("No IFTTT api key for %s", target)
            continue
        target_keys[target] = api_keys[target]

    try:
        for target, key in target_keys.items():
            res = pyfttt.send_event(key, event, value1, value2, value3)
            if res.status_code != HTTPStatus.OK:
                _LOGGER.error("IFTTT reported error sending event to %s", target)
    except requests.exceptions.RequestException as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="trigger_failed",
        ) from err


async def _push_state_update(service: ServiceCall) -> None:
    """Set the service state as device state attribute."""
    entity_ids = service.data.get(CommonServiceArgument.ENTITY_ID)
    state = service.data.get(IftttServiceArgument.STATE)
    devices = service.hass.data.get(DATA_IFTTT_ALARM, [])
    if entity_ids:
        devices = [d for d in devices if d.entity_id in entity_ids]

    for device in devices:
        device.push_alarm_state(state)
        device.async_schedule_update_ha_state()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the IFTTT integration."""
    hass.services.async_register(
        DOMAIN, IftttService.TRIGGER, _trigger_service, schema=SERVICE_TRIGGER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        IftttService.PUSH_ALARM_STATE,
        _push_state_update,
        schema=PUSH_ALARM_STATE_SERVICE_SCHEMA,
    )
