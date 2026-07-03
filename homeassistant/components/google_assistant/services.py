"""Support for Google Assistant services."""

import logging

from homeassistant.core import HomeAssistant, ServiceCall, callback

from .const import DOMAIN, SERVICE_REQUEST_SYNC

_LOGGER = logging.getLogger(__name__)


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register Google Assistant services."""

    async def request_sync_service_handler(call: ServiceCall) -> None:
        """Handle request sync service calls."""
        agent_user_id = call.data.get("agent_user_id") or call.context.user_id

        if agent_user_id is None:
            _LOGGER.warning(
                "No agent_user_id supplied for request_sync. Call as a user or pass in"
                " user id as agent_user_id"
            )
            return

        if not (entries := hass.config_entries.async_loaded_entries(DOMAIN)):
            _LOGGER.warning("No Google Assistant config entry loaded for request_sync")
            return

        await entries[0].runtime_data.async_sync_entities(agent_user_id)

    hass.services.async_register(
        DOMAIN, SERVICE_REQUEST_SYNC, request_sync_service_handler
    )
