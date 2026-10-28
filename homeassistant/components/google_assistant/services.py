"""Support for Google Assistant services."""

from enum import StrEnum
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import service

from .const import CONF_SERVICE_ACCOUNT, DATA_CONFIG, DOMAIN
from .http import GoogleConfig

_LOGGER = logging.getLogger(__name__)


class GoogleAssistantService(StrEnum):
    """Store keys for Google Assistant services."""

    RELOAD = "reload"
    REQUEST_SYNC = "request_sync"


class GoogleAssistantServiceArgument(StrEnum):
    """Store keys for Google Assistant service arguments."""

    AGENT_USER_ID = "agent_user_id"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Google Assistant services."""

    async def request_sync_service_handler(call: ServiceCall) -> None:
        """Handle request sync service calls."""
        agent_user_id = (
            call.data.get(GoogleAssistantServiceArgument.AGENT_USER_ID)
            or call.context.user_id
        )

        if agent_user_id is None:
            _LOGGER.warning(
                "No agent_user_id supplied for request_sync. Call as a user or pass in"
                " user id as agent_user_id"
            )
            return

        entry: ConfigEntry[GoogleConfig] = service.async_get_config_entry(
            hass, DOMAIN, None
        )
        await entry.runtime_data.async_sync_entities(agent_user_id)

    if CONF_SERVICE_ACCOUNT in hass.data[DATA_CONFIG]:
        hass.services.async_register(
            DOMAIN, GoogleAssistantService.REQUEST_SYNC, request_sync_service_handler
        )

    async def reload_service_handler(call: ServiceCall) -> None:
        """Reload the YAML configuration and sync the entities to Google."""
        entry: ConfigEntry[GoogleConfig] = service.async_get_config_entry(
            hass, DOMAIN, None
        )
        if await entry.runtime_data.async_reload_yaml():
            await entry.runtime_data.async_sync_entities_all()

    service.async_register_admin_service(
        hass, DOMAIN, GoogleAssistantService.RELOAD, reload_service_handler
    )
