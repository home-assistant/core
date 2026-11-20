"""Service registration for PlayStation Network integration."""

from enum import StrEnum

import probatio

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.selector import MediaSelector

from .const import DOMAIN


class PlayStationNetworkService(StrEnum):
    """Store keys for PlayStation Network services."""

    SEND_IMAGE = "send_image"


class PlayStationNetworkServiceArgument(StrEnum):
    """Store keys for PlayStation Network service arguments."""

    IMAGE = "image"


SERVICE_SEND_IMAGE_SCHEMA = cv.make_entity_service_schema(
    {
        probatio.Required(PlayStationNetworkServiceArgument.IMAGE): MediaSelector(
            {"accept": ["*"]}
        ),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for PlayStation Network integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        PlayStationNetworkService.SEND_IMAGE,
        entity_domain=NOTIFY_DOMAIN,
        schema=SERVICE_SEND_IMAGE_SCHEMA,
        func="send_image",
    )
