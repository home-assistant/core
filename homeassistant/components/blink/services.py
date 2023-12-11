"""Services for the Blink integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PIN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv

from .const import ATTR_CONFIG_ENTRY_ID, DOMAIN, SERVICE_REFRESH, SERVICE_SEND_PIN

SERVICE_UPDATE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): vol.All(cv.ensure_list, [cv.string]),
    }
)
SERVICE_SEND_PIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_PIN): cv.string,
    }
)


def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Blink integration."""

    async def send_pin(call: ServiceCall):
        """Call blink to send new pin."""
        for entry_id in call.data[ATTR_CONFIG_ENTRY_ID]:
            try:
                coordinator = hass.data[DOMAIN][entry_id]
            except KeyError as ex:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="integration_not_found",
                    translation_placeholders={"target": DOMAIN},
                ) from ex
            if coordinator.config_entry.state != ConfigEntryState.LOADED:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="not_loaded",
                    translation_placeholders={"target": coordinator.config_entry.title},
                )

            await coordinator.api.auth.send_auth_key(
                coordinator.api,
                call.data[CONF_PIN],
            )

    async def blink_refresh(call: ServiceCall):
        """Call blink to refresh info."""
        for entry_id in call.data[ATTR_CONFIG_ENTRY_ID]:
            try:
                coordinator = hass.data[DOMAIN][entry_id]
            except KeyError as ex:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="integration_not_found",
                    translation_placeholders={"target": DOMAIN},
                ) from ex
            if coordinator.config_entry.state != ConfigEntryState.LOADED:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="not_loaded",
                    translation_placeholders={"target": coordinator.config_entry.title},
                )
            await coordinator.api.refresh(force_cache=True)

    # Register all the above services
    # Refresh service is depreciated and will be removed on 6/2024
    service_mapping = [
        (blink_refresh, SERVICE_REFRESH, SERVICE_UPDATE_SCHEMA),
        (send_pin, SERVICE_SEND_PIN, SERVICE_SEND_PIN_SCHEMA),
    ]

    for service_handler, service_name, schema in service_mapping:
        hass.services.async_register(
            DOMAIN,
            service_name,
            service_handler,
            schema=schema,
        )
