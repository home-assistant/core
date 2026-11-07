"""Services for the Hunter Hydrawise integration."""

from enum import StrEnum

import probatio

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN


class HydrawiseService(StrEnum):
    """Store keys for Hunter Hydrawise services."""

    START_WATERING = "start_watering"
    SUSPEND = "suspend"
    RESUME = "resume"


class HydrawiseServiceArgument(StrEnum):
    """Store keys for Hunter Hydrawise service arguments."""

    DURATION = "duration"
    UNTIL = "until"


SCHEMA_START_WATERING: VolDictType = {
    probatio.Optional(HydrawiseServiceArgument.DURATION): probatio.All(
        probatio.Coerce(int), probatio.Range(min=0, max=1440)
    ),
}
SCHEMA_SUSPEND: VolDictType = {
    probatio.Required(HydrawiseServiceArgument.UNTIL): cv.datetime,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Hunter Hydrawise integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        HydrawiseService.RESUME,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=None,
        func="resume",
        entity_device_classes=(BinarySensorDeviceClass.RUNNING,),
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        HydrawiseService.START_WATERING,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=SCHEMA_START_WATERING,
        func="start_watering",
        entity_device_classes=(BinarySensorDeviceClass.RUNNING,),
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        HydrawiseService.SUSPEND,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=SCHEMA_SUSPEND,
        func="suspend",
        entity_device_classes=(BinarySensorDeviceClass.RUNNING,),
    )
