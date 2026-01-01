"""Services for the Blink integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_PIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, issue_registry as ir

from .const import DOMAIN, SERVICE_SEND_PIN

SERVICE_SEND_PIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_PIN): cv.string,
    }
)


async def _send_pin(call: ServiceCall) -> None:
    """Call blink to send new pin."""
    # Create repair issue to inform user about service removal
    ir.async_create_issue(
        call.hass,
        DOMAIN,
        "service_send_pin_deprecation",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.ERROR,
        breaks_in_ha_version="2026.5.0",
        translation_key="service_send_pin_deprecation",
        translation_placeholders={"service_name": f"{DOMAIN}.{SERVICE_SEND_PIN}"},
    )

    # Service has been removed - raise exception
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="service_removed",
        translation_placeholders={"service_name": f"{DOMAIN}.{SERVICE_SEND_PIN}"},
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
