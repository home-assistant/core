"""Services for the AdGuard Home integration."""

from typing import TYPE_CHECKING

from adguardhome import AdGuardHome
import probatio

from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_FORCE,
    DOMAIN,
    SERVICE_ADD_URL,
    SERVICE_DISABLE_URL,
    SERVICE_ENABLE_URL,
    SERVICE_REFRESH,
    SERVICE_REMOVE_URL,
)

if TYPE_CHECKING:
    from . import AdGuardConfigEntry

SERVICE_URL_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_URL): probatio.Any(cv.url, cv.path)}
)
SERVICE_ADD_URL_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_NAME): cv.string,
        probatio.Required(CONF_URL): probatio.Any(cv.url, cv.path),
    }
)
SERVICE_REFRESH_SCHEMA = probatio.Schema(
    {probatio.Optional(CONF_FORCE, default=False): cv.boolean}
)


def _get_adguard_instances(hass: HomeAssistant) -> list[AdGuardHome]:
    """Get the AdGuardHome instances."""
    entries: list[AdGuardConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="config_entry_not_loaded"
        )
    return [entry.runtime_data.client for entry in entries]


async def _add_url(call: ServiceCall) -> None:
    """Service call to add a new filter subscription to AdGuard Home."""
    for adguard in _get_adguard_instances(call.hass):
        await adguard.filtering.blocklists.add(
            call.data[CONF_URL], name=call.data[CONF_NAME]
        )


async def _remove_url(call: ServiceCall) -> None:
    """Service call to remove a filter subscription from AdGuard Home."""
    for adguard in _get_adguard_instances(call.hass):
        await adguard.filtering.blocklists.remove(call.data[CONF_URL])


async def _enable_url(call: ServiceCall) -> None:
    """Service call to enable a filter subscription in AdGuard Home."""
    for adguard in _get_adguard_instances(call.hass):
        await adguard.filtering.blocklists.enable(call.data[CONF_URL])


async def _disable_url(call: ServiceCall) -> None:
    """Service call to disable a filter subscription in AdGuard Home."""
    for adguard in _get_adguard_instances(call.hass):
        await adguard.filtering.blocklists.disable(call.data[CONF_URL])


async def _refresh(call: ServiceCall) -> None:
    """Service call to refresh the filter subscriptions in AdGuard Home."""
    for adguard in _get_adguard_instances(call.hass):
        # AdGuard Home always forces a refresh, so the force option does
        # nothing, but is kept so existing automations keep working.
        await adguard.filtering.blocklists.refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the AdGuard Home integration."""

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_URL, _add_url, schema=SERVICE_ADD_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_URL, _remove_url, schema=SERVICE_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ENABLE_URL, _enable_url, schema=SERVICE_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DISABLE_URL, _disable_url, schema=SERVICE_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, _refresh, schema=SERVICE_REFRESH_SCHEMA
    )
