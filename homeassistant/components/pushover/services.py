"""Services for the Pushover integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import ATTR_ENTRY_ID, ATTR_TAG, DOMAIN, SERVICE_CANCEL

if TYPE_CHECKING:
    from . import PushoverConfigEntry

SERVICE_CANCEL_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_ENTRY_ID): cv.string,
        probatio.Optional(ATTR_TAG): cv.string,
    }
)


async def _async_cancel_service_handler(call: ServiceCall) -> None:
    """Cancel emergency notifications for the targeted config entry."""
    hass = call.hass
    entry_id: str = call.data[ATTR_ENTRY_ID]
    entry: PushoverConfigEntry | None = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        raise ServiceValidationError(f"Pushover config entry {entry_id} does not exist")

    notify_service = entry.runtime_data.notify_service
    if notify_service is None:
        raise ServiceValidationError(
            f"Pushover config entry {entry_id} has no notify service set up"
        )

    tag: str = call.data.get(ATTR_TAG, "")
    await hass.async_add_executor_job(notify_service.cancel_by_tag, tag)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Pushover integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL,
        _async_cancel_service_handler,
        schema=SERVICE_CANCEL_SCHEMA,
    )
