"""Services for the Humidifier integration."""

import logging
from typing import TYPE_CHECKING

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    DATA_COMPONENT,
    DOMAIN,
    HumidifierEntityFeature,
    HumidifierService,
    HumidifierServiceArgument,
)

if TYPE_CHECKING:
    from .entity import HumidifierEntity

_LOGGER = logging.getLogger(__name__)


async def _async_service_humidity_set(
    entity: HumidifierEntity, service_call: ServiceCall
) -> None:
    """Handle set humidity service."""
    humidity = service_call.data[HumidifierServiceArgument.HUMIDITY]
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

    component.async_register_entity_service(
        HumidifierService.TURN_ON, None, "async_turn_on"
    )
    component.async_register_entity_service(
        HumidifierService.TURN_OFF, None, "async_turn_off"
    )
    component.async_register_entity_service(
        HumidifierService.TOGGLE, None, "async_toggle"
    )
    component.async_register_entity_service(
        HumidifierService.SET_MODE,
        {probatio.Required(HumidifierServiceArgument.MODE): cv.string},
        "async_set_mode",
        [HumidifierEntityFeature.MODES],
    )
    component.async_register_entity_service(
        HumidifierService.SET_HUMIDITY,
        {
            probatio.Required(HumidifierServiceArgument.HUMIDITY): probatio.All(
                probatio.Coerce(int), probatio.Percentage()
            )
        },
        _async_service_humidity_set,
    )
