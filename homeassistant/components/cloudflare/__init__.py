"""Cloudflare integration: multi-zone DDNS and proxy control."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
import socket
from typing import Any

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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util.location import async_detect_location_info
from homeassistant.util.network import is_ipv4_address

from .const import (
    CONF_DOMAINS,
    CONF_RECORDS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SERVICE_UPDATE_RECORDS,
)
from .helpers import async_create_a_record

_LOGGER = logging.getLogger(__name__)


@dataclass
class CloudflareRuntimeData:
    """Runtime data for Cloudflare config entry."""

    client: pycfdns.Client
    dns_zone: pycfdns.ZoneModel
    coordinator: DataUpdateCoordinator[dict[str, Any]]
    api_token: str


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

    async def _async_get_external_ipv4() -> str:
        loc_session = async_get_clientsession(hass, family=socket.AF_INET)
        location_info = await async_detect_location_info(loc_session)
        if not location_info or not is_ipv4_address(location_info.ip):
            raise HomeAssistantError("Could not get external IPv4 address")
        return location_info.ip

    async def _async_coordinator_update() -> dict[str, Any]:
        """Fetch and synchronize DNS records for configured domains."""
        zone_id = dns_zone["id"]
        external_ip = await _async_get_external_ipv4()
        configured_domains: list[str] = (
            entry.data.get(CONF_DOMAINS) or entry.data.get(CONF_RECORDS) or []
        )

        # Retrieve existing A records for zone
        records = await client.list_dns_records(zone_id=zone_id, type="A")
        record_index: dict[str, pycfdns.RecordModel] = {r["name"]: r for r in records}
        results: dict[str, Any] = {}

        tasks: list[asyncio.Task] = []
        for domain in configured_domains:
            record = record_index.get(domain)
            if record is None:
                # Create missing record (proxied True by default)
                tasks.append(
                    asyncio.create_task(
                        async_create_a_record(
                            session=session,
                            api_token=entry.data[CONF_API_TOKEN],
                            zone_id=zone_id,
                            name=domain,
                            content=external_ip,
                            proxied=True,
                        )
                    )
                )
            elif record["content"] != external_ip:
                # Update IP while keeping proxied state
                tasks.append(
                    asyncio.create_task(
                        client.update_dns_record(
                            zone_id=zone_id,
                            record_id=record["id"],
                            record_content=external_ip,
                            record_name=record["name"],
                            record_type=record["type"],
                            record_proxied=record["proxied"],
                        )
                    )
                )
            results[domain] = record or None

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Refresh records after modifications
        refreshed = await client.list_dns_records(zone_id=zone_id, type="A")
        refreshed_index = {r["name"]: r for r in refreshed}
        for domain in configured_domains:
            results[domain] = refreshed_index.get(domain)

        return {
            "external_ip": external_ip,
            "records": results,
            "updated_at": dt_util.utcnow(),
        }

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"cloudflare-{dns_zone['name']}",
        update_method=_async_coordinator_update,
        update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL),
    )

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
