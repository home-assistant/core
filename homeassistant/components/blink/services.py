"""Services for the Blink integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import ATTR_CONFIG_ENTRY_ID, DOMAIN, SERVICE_SEND_PIN
from .coordinator import BlinkConfigEntry

SERVICE_SEND_PIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_PIN): cv.string,
    }
)


async def _send_pin(call: ServiceCall) -> None:
    """Call blink to send new pin."""
    config_entry: BlinkConfigEntry | None
    for entry_id in call.data[ATTR_CONFIG_ENTRY_ID]:
        if not (config_entry := call.hass.config_entries.async_get_entry(entry_id)):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="integration_not_found",
                translation_placeholders={"target": DOMAIN},
            )
        if config_entry.state != ConfigEntryState.LOADED:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="not_loaded",
                translation_placeholders={"target": config_entry.title},
            )
        coordinator = config_entry.runtime_data
        await coordinator.api.auth.send_auth_key(
            coordinator.api,
            call.data[CONF_PIN],
        )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Blink integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_PIN,
        _send_pin,
        schema=SERVICE_SEND_PIN_SCHEMA,
    )
