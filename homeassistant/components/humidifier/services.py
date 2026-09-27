"""Services for the Humidifier integration."""

import logging
from typing import TYPE_CHECKING

import probatio

from homeassistant.const import (
    ATTR_MODE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_HUMIDITY,
    DATA_COMPONENT,
    DOMAIN,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    HumidifierEntityFeature,
)

if TYPE_CHECKING:
    from . import HumidifierEntity

_LOGGER = logging.getLogger(__name__)


async def _async_service_humidity_set(
    entity: HumidifierEntity, service_call: ServiceCall
) -> None:
    """Handle set humidity service."""
    humidity = service_call.data[ATTR_HUMIDITY]
    min_humidity = entity.min_humidity
    max_humidity = entity.max_humidity
    _LOGGER.debug(
        "Check valid humidity %d in range %d - %d",
        humidity,
        min_humidity,
        max_humidity,
    )
    if humidity < min_humidity or humidity > max_humidity:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="humidity_out_of_range",
            translation_placeholders={
                "humidity": str(humidity),
                "min_humidity": str(min_humidity),
                "max_humidity": str(max_humidity),
            },
        )

    await entity.async_set_humidity(humidity)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the humidifier services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(SERVICE_TURN_ON, None, "async_turn_on")
    component.async_register_entity_service(SERVICE_TURN_OFF, None, "async_turn_off")
    component.async_register_entity_service(SERVICE_TOGGLE, None, "async_toggle")
    component.async_register_entity_service(
        SERVICE_SET_MODE,
        {probatio.Required(ATTR_MODE): cv.string},
        "async_set_mode",
        [HumidifierEntityFeature.MODES],
    )
    component.async_register_entity_service(
        SERVICE_SET_HUMIDITY,
        {
            probatio.Required(ATTR_HUMIDITY): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0, max=100)
            )
        },
        _async_service_humidity_set,
    )
