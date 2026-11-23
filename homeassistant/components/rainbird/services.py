"""Rain Bird Irrigation system services."""

import probatio

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN, RainbirdService, RainbirdServiceArgument

SERVICE_SCHEMA_IRRIGATION: VolDictType = {
    probatio.Required(RainbirdServiceArgument.DURATION): cv.positive_float,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        RainbirdService.START_IRRIGATION,
        entity_domain=SWITCH_DOMAIN,
        schema=SERVICE_SCHEMA_IRRIGATION,
        func="async_turn_on",
    )
