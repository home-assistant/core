"""Services for the IFTTT integration."""

from http import HTTPStatus
import logging

import probatio
import pyfttt
import requests

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_EVENT,
    ATTR_TARGET,
    ATTR_VALUE1,
    ATTR_VALUE2,
    ATTR_VALUE3,
    DATA_API_KEYS,
    DOMAIN,
    SERVICE_TRIGGER,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_TRIGGER_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_EVENT): cv.string,
        probatio.Optional(ATTR_TARGET): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Optional(ATTR_VALUE1): cv.string,
        probatio.Optional(ATTR_VALUE2): cv.string,
        probatio.Optional(ATTR_VALUE3): cv.string,
    }
)


def _trigger_service(call: ServiceCall) -> None:
    """Handle IFTTT trigger service calls."""
    api_keys = call.hass.data.get(DATA_API_KEYS, {})
    event = call.data[ATTR_EVENT]
    targets = call.data.get(ATTR_TARGET, list(api_keys))
    value1 = call.data.get(ATTR_VALUE1)
    value2 = call.data.get(ATTR_VALUE2)
    value3 = call.data.get(ATTR_VALUE3)

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


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the IFTTT integration."""
    hass.services.async_register(
        DOMAIN, SERVICE_TRIGGER, _trigger_service, schema=SERVICE_TRIGGER_SCHEMA
    )
