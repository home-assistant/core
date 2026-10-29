"""Services for the Google Cast integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, instance_id
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN, SIGNAL_HASS_CAST_SHOW_VIEW, HomeAssistantControllerData

if TYPE_CHECKING:
    from . import CastConfigEntry

SERVICE_SHOW_VIEW = "show_lovelace_view"
ATTR_VIEW_PATH = "view_path"
ATTR_URL_PATH = "dashboard_path"
NO_URL_AVAILABLE_ERROR = (
    "Home Assistant Cast requires your instance to be reachable via HTTPS. Enable Home"
    " Assistant Cloud or set up an external URL with valid SSL certificates"
)


async def _handle_show_view(call: ServiceCall) -> None:
    """Handle a Show View service call."""
    hass = call.hass
    if not (entries := hass.config_entries.async_loaded_entries(DOMAIN)):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="not_loaded"
        )
    entry: CastConfigEntry = entries[0]
    try:
        hass_url = get_url(hass, require_ssl=True, prefer_external=True)
    except NoURLAvailableError as err:
        raise HomeAssistantError(NO_URL_AVAILABLE_ERROR) from err

    hass_uuid = await instance_id.async_get(hass)

    controller_data = HomeAssistantControllerData(
        # If you are developing Home Assistant Cast, uncomment and set to
        # your dev app id.
        # app_id="5FE44367",
        hass_url=hass_url,
        hass_uuid=hass_uuid,
        client_id=None,
        refresh_token=entry.runtime_data.refresh_token,
    )

    async_dispatcher_send(
        hass,
        SIGNAL_HASS_CAST_SHOW_VIEW,
        controller_data,
        call.data[ATTR_ENTITY_ID],
        call.data[ATTR_VIEW_PATH],
        call.data.get(ATTR_URL_PATH),
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Google Cast integration."""
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SHOW_VIEW,
        _handle_show_view,
        probatio.Schema(
            {
                ATTR_ENTITY_ID: cv.entity_id,
                ATTR_VIEW_PATH: str,
                probatio.Optional(ATTR_URL_PATH): str,
            }
        ),
    )
