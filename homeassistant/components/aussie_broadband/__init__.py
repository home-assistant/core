"""The Aussie Broadband integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientError
from aussiebb.asyncio import AussieBB
from aussiebb.const import FETCH_TYPES, NBN_TYPES, PHONE_TYPES
from aussiebb.exceptions import AuthenticationException, UnrecognisedServiceType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, SERVICE_ID

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


# Backport for the pyaussiebb=0.0.15 validate_service_type method
def validate_service_type(service: dict[str, Any]) -> None:
    """Check the service types against known types."""

    if "type" not in service:
        raise ValueError("Field 'type' not found in service data")
    if service["type"] not in NBN_TYPES + PHONE_TYPES + ["Hardware"]:
        raise UnrecognisedServiceType(
            f"Service type {service['type']=} {service['name']=} - not recognised - ",
            "please report this at https://github.com/yaleman/aussiebb/issues/new",
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aussie Broadband from a config entry."""
    # Login to the Aussie Broadband API and retrieve the current service list
    client = AussieBB(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        async_get_clientsession(hass),
    )
    # Overwrite the pyaussiebb=0.0.15 validate_service_type method with backport
    # Required until pydantic 2.x is supported
    client.validate_service_type = validate_service_type
    try:
        await client.login()
        services = await client.get_services(drop_types=FETCH_TYPES)
    except AuthenticationException as exc:
        raise ConfigEntryAuthFailed() from exc
    except ClientError as exc:
        raise ConfigEntryNotReady() from exc

    # Create an appropriate refresh function
    def update_data_factory(service_id):
        async def async_update_data():
            try:
                return await client.get_usage(service_id)
            except UnrecognisedServiceType as err:
                raise UpdateFailed(
                    f"Service {service_id} of type '{services[service_id]['type']}' was"
                    " unrecognised"
                ) from err

        return async_update_data

    # Initiate a Data Update Coordinator for each service
    for service in services:
        service["coordinator"] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=service["service_id"],
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL),
            update_method=update_data_factory(service[SERVICE_ID]),
        )
        await service["coordinator"].async_config_entry_first_refresh()

    # Setup the integration
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "services": services,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
