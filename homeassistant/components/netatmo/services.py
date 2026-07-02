"""Services for the Netatmo integration."""

import logging

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .data_handler import NetatmoConfigEntry
from .webhook import async_register_webhook, async_unregister_webhook

_LOGGER = logging.getLogger(__name__)

SERVICE_REGISTER_WEBHOOK = "register_webhook"
SERVICE_UNREGISTER_WEBHOOK = "unregister_webhook"

WEBHOOK_SERVICES_DEPRECATION_VERSION = "2027.2.0"


def _get_loaded_entry(hass: HomeAssistant) -> NetatmoConfigEntry:
    """Return the loaded config entry or raise if unavailable."""
    entry: NetatmoConfigEntry | None = (
        hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, DOMAIN)
    )
    if entry is None or entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
        )
    return entry


def _deprecate(hass: HomeAssistant, service: str) -> None:
    """Warn and raise a repair issue for the deprecated webhook actions."""
    _LOGGER.warning(
        "The %s.%s action is deprecated and will be removed in %s; the webhook "
        "is managed automatically",
        DOMAIN,
        service,
        WEBHOOK_SERVICES_DEPRECATION_VERSION,
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_service_{service}",
        breaks_in_ha_version=WEBHOOK_SERVICES_DEPRECATION_VERSION,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_webhook_service",
        translation_placeholders={"service": f"{DOMAIN}.{service}"},
    )


async def _register_webhook(call: ServiceCall) -> None:
    """Handle the deprecated register_webhook action."""
    _deprecate(call.hass, SERVICE_REGISTER_WEBHOOK)
    entry = _get_loaded_entry(call.hass)
    # Drop any existing registration first so re-registering an already-active
    # webhook does not raise "Handler is already defined!".
    await async_unregister_webhook(call.hass, entry)
    await async_register_webhook(call.hass, entry)


async def _unregister_webhook(call: ServiceCall) -> None:
    """Handle the deprecated unregister_webhook action."""
    _deprecate(call.hass, SERVICE_UNREGISTER_WEBHOOK)
    await async_unregister_webhook(call.hass, _get_loaded_entry(call.hass))


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Netatmo services."""
    hass.services.async_register(DOMAIN, SERVICE_REGISTER_WEBHOOK, _register_webhook)
    hass.services.async_register(
        DOMAIN, SERVICE_UNREGISTER_WEBHOOK, _unregister_webhook
    )
