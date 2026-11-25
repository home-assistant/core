"""Services for the Govee light local integration."""

from enum import StrEnum

import probatio

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN, LightServiceArgument
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN


class GoveeLocalService(StrEnum):
    """Govee light local services."""

    SET_SEGMENT_COLOR = "set_segment_color"


class GoveeLocalServiceArgument(StrEnum):
    """Govee light local service arguments."""

    SEGMENTS = "segments"


SET_SEGMENT_COLOR_SCHEMA: VolDictType = {
    probatio.Required(GoveeLocalServiceArgument.SEGMENTS): probatio.All(
        probatio.EnsureList(),
        probatio.Length(min=1),
        [probatio.All(probatio.Coerce(int), probatio.Range(min=1))],
        probatio.Unique(),
    ),
    probatio.Required(LightServiceArgument.RGB_COLOR): probatio.All(
        probatio.Coerce(tuple), probatio.ExactSequence((cv.byte,) * 3)
    ),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services of Govee light local."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        GoveeLocalService.SET_SEGMENT_COLOR,
        entity_domain=LIGHT_DOMAIN,
        schema=SET_SEGMENT_COLOR_SCHEMA,
        func="async_set_segment_color",
    )
