"""Services for the Belkin WeMo integration."""

import probatio

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service
from homeassistant.helpers.typing import VolDictType

from .const import (
    ATTR_TARGET_HUMIDITY,
    DOMAIN,
    SERVICE_RESET_FILTER_LIFE,
    SERVICE_SET_HUMIDITY,
)

SET_HUMIDITY_SCHEMA: VolDictType = {
    probatio.Required(ATTR_TARGET_HUMIDITY): probatio.All(
        probatio.Coerce(float), probatio.Percentage()
    ),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Belkin WeMo integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_HUMIDITY,
        entity_domain=FAN_DOMAIN,
        schema=SET_HUMIDITY_SCHEMA,
        func="async_set_humidity",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_RESET_FILTER_LIFE,
        entity_domain=FAN_DOMAIN,
        schema=None,
        func="async_reset_filter_life",
    )
