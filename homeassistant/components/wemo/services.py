"""Services for the Belkin WeMo integration."""

from enum import StrEnum

import probatio

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN


class WemoService(StrEnum):
    """Store keys for WeMo services."""

    SET_HUMIDITY = "set_humidity"
    RESET_FILTER_LIFE = "reset_filter_life"


class WemoServiceArgument(StrEnum):
    """Store keys for WeMo service arguments."""

    TARGET_HUMIDITY = "target_humidity"


SET_HUMIDITY_SCHEMA: VolDictType = {
    probatio.Required(WemoServiceArgument.TARGET_HUMIDITY): probatio.All(
        probatio.Coerce(float), probatio.Percentage()
    ),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Belkin WeMo integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        WemoService.SET_HUMIDITY,
        entity_domain=FAN_DOMAIN,
        schema=SET_HUMIDITY_SCHEMA,
        func="async_set_humidity",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        WemoService.RESET_FILTER_LIFE,
        entity_domain=FAN_DOMAIN,
        schema=None,
        func="async_reset_filter_life",
    )
