"""Services for the Pushover integration."""

from enum import StrEnum
from typing import TYPE_CHECKING

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class PushoverService(StrEnum):
    """Store keys for Pushover services."""

    CANCEL = "cancel"


class PushoverServiceArgument(StrEnum):
    """Store keys for Pushover service arguments."""

    ENTRY_ID = "entry_id"
    TAG = "tag"


if TYPE_CHECKING:
    from . import PushoverConfigEntry

SERVICE_CANCEL_SCHEMA = probatio.Schema(
    {
        probatio.Required(PushoverServiceArgument.ENTRY_ID): cv.string,
        probatio.Optional(PushoverServiceArgument.TAG): cv.string,
    }
)


async def _async_cancel_service_handler(call: ServiceCall) -> None:
    """Cancel emergency notifications for the targeted config entry."""
    hass = call.hass
    entry_id: str = call.data[PushoverServiceArgument.ENTRY_ID]
    entry: PushoverConfigEntry = service.async_get_config_entry(hass, DOMAIN, entry_id)

    notify_service = entry.runtime_data.notify_service
    if notify_service is None:
        raise ServiceValidationError(
            f"Pushover config entry {entry_id} has no notify service set up"
        )

    tag: str = call.data.get(PushoverServiceArgument.TAG, "")
    await hass.async_add_executor_job(notify_service.cancel_by_tag, tag)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Pushover integration."""

    hass.services.async_register(
        DOMAIN,
        PushoverService.CANCEL,
        _async_cancel_service_handler,
        schema=SERVICE_CANCEL_SCHEMA,
    )
