"""Services for the Hunter Hydrawise integration."""

import probatio

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN, SERVICE_RESUME, SERVICE_START_WATERING, SERVICE_SUSPEND

SCHEMA_START_WATERING: VolDictType = {
    probatio.Optional("duration"): probatio.All(
        probatio.Coerce(int), probatio.Range(min=0, max=1440)
    ),
}
SCHEMA_SUSPEND: VolDictType = {
    probatio.Required("until"): cv.datetime,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Hunter Hydrawise integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_RESUME,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=None,
        func="resume",
        entity_device_classes=(BinarySensorDeviceClass.RUNNING,),
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_START_WATERING,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=SCHEMA_START_WATERING,
        func="start_watering",
        entity_device_classes=(BinarySensorDeviceClass.RUNNING,),
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SUSPEND,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=SCHEMA_SUSPEND,
        func="suspend",
        entity_device_classes=(BinarySensorDeviceClass.RUNNING,),
    )
