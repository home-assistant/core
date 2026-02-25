"""Cloudflare integration: multi-zone DDNS and proxy control."""

from __future__ import annotations

import logging

import pycfdns

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_ZONE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DOMAINS, CONF_RECORDS, DOMAIN, PLATFORMS, SERVICE_UPDATE_RECORDS
from .coordinator import CloudflareCoordinator, CloudflareRuntimeData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = CloudflareRuntimeData(
        client=client,
        dns_zone=dns_zone,
        coordinator=coordinator,
        api_token=entry.data[CONF_API_TOKEN],
    )

    async def update_records_service(call: ServiceCall) -> None:
        """Manual trigger for update cycle.

        Provides a safer manual refresh catching Cloudflare-specific errors.
        """
        try:
            await coordinator.async_request_refresh()
        except pycfdns.AuthenticationException as err:
            _LOGGER.error(
                "Authentication failed updating zone %s manually: %s",
                dns_zone["name"],
                err,
            )
            raise HomeAssistantError("Cloudflare authentication failed") from err
        except pycfdns.ComunicationException as err:
            _LOGGER.error(
                "Communication error updating zone %s manually: %s",
                dns_zone["name"],
                err,
            )
            raise HomeAssistantError("Cloudflare communication error") from err
        except HomeAssistantError:
            # Already meaningful, just bubble up
            raise
        except Exception as err:
            _LOGGER.exception(
                "Unexpected error during manual update for zone %s", dns_zone["name"]
            )
            raise HomeAssistantError("Unexpected Cloudflare update error") from err

    hass.services.async_register(DOMAIN, SERVICE_UPDATE_RECORDS, update_records_service)

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
