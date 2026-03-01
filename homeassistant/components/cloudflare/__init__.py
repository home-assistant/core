"""Cloudflare integration: multi-zone DDNS and proxy control."""

from __future__ import annotations

import logging

import pycfdns

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_TOKEN, CONF_ZONE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CONF_DOMAINS, CONF_RECORDS, DOMAIN, PLATFORMS, SERVICE_UPDATE_RECORDS
from .coordinator import (
    CloudflareConfigEntry,
    CloudflareCoordinator,
    CloudflareRuntimeData,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Cloudflare component."""

    async def update_records_service(call: ServiceCall) -> None:
        """Manual trigger for update cycle.

        Provides a safer manual refresh catching Cloudflare-specific errors.
        """
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is not ConfigEntryState.LOADED:
                continue

            runtime_data: CloudflareRuntimeData = entry.runtime_data
            coordinator = runtime_data.coordinator
            dns_zone = runtime_data.dns_zone

            await coordinator.async_request_refresh()

            if coordinator.last_update_success:
                continue

            err = coordinator.last_exception

            if isinstance(err, pycfdns.AuthenticationException):
                _LOGGER.error(
                    "Authentication failed updating zone %s manually: %s",
                    dns_zone["name"],
                    err,
                )
                raise HomeAssistantError("Cloudflare authentication failed") from err

            if isinstance(err, pycfdns.ComunicationException):
                _LOGGER.error(
                    "Communication error updating zone %s manually: %s",
                    dns_zone["name"],
                    err,
                )
                raise HomeAssistantError("Cloudflare communication error") from err

            if isinstance(err, UpdateFailed):
                _LOGGER.error(
                    "Error updating zone %s manually: %s",
                    dns_zone["name"],
                    err,
                )
                raise HomeAssistantError(str(err)) from err

            if err is not None:
                _LOGGER.exception(
                    "Unexpected error during manual update for zone %s",
                    dns_zone["name"],
                )
                raise HomeAssistantError("Unexpected Cloudflare update error") from err

            # Refresh failed but no exception was recorded
            _LOGGER.error(
                "Unknown error during manual update for zone %s", dns_zone["name"]
            )
            raise HomeAssistantError("Unknown Cloudflare update error")

    hass.services.async_register(DOMAIN, SERVICE_UPDATE_RECORDS, update_records_service)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: CloudflareConfigEntry) -> bool:
    """Set up Cloudflare from a config entry."""
    session = async_get_clientsession(hass)
    client = pycfdns.Client(
        api_token=entry.data[CONF_API_TOKEN],
        client_session=session,
    )

    try:
        dns_zones = await client.list_zones()
        dns_zone = next(
            zone for zone in dns_zones if zone["name"] == entry.data[CONF_ZONE]
        )
    except pycfdns.AuthenticationException as error:
        raise ConfigEntryAuthFailed from error
    except pycfdns.ComunicationException as error:
        raise ConfigEntryNotReady from error

    coordinator = CloudflareCoordinator(hass, entry, client, dns_zone)

    await coordinator.async_refresh()

    if isinstance(coordinator.last_exception, ConfigEntryAuthFailed):
        raise coordinator.last_exception

    entry.runtime_data = CloudflareRuntimeData(
        client=client,
        dns_zone=dns_zone,
        coordinator=coordinator,
        api_token=entry.data[CONF_API_TOKEN],
    )

    # Forward platforms (switch entities per domain)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Cloudflare config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry data keys to new domains key."""
    data = {**entry.data}
    if CONF_RECORDS in data and CONF_DOMAINS not in data:
        data[CONF_DOMAINS] = data[CONF_RECORDS]
        hass.config_entries.async_update_entry(entry, data=data)
        _LOGGER.info("Migrated Cloudflare entry %s to new domains key", entry.entry_id)
    return True
