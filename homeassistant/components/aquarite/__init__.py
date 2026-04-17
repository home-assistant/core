"""The Aquarite integration."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
import logging

from aioaquarite import AquariteAuth, AquariteClient, AquariteError, AuthenticationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import HEALTH_CHECK_INTERVAL
from .coordinator import AquariteDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass
class AquariteData:
    """Runtime data for an Aquarite account (holds one coordinator per pool)."""

    auth: AquariteAuth
    api: AquariteClient
    coordinators: dict[str, AquariteDataUpdateCoordinator] = field(default_factory=dict)
    health_task: asyncio.Task[None] | None = None
    token_task: asyncio.Task[None] | None = None


type AquariteConfigEntry = ConfigEntry[AquariteData]


async def async_setup_entry(hass: HomeAssistant, entry: AquariteConfigEntry) -> bool:
    """Set up Aquarite from a config entry.

    One config entry represents a Hayward account; the account can contain
    multiple pools, each exposed as a separate device.
    """
    user_config = entry.data
    session = async_get_clientsession(hass)

    auth = AquariteAuth(session, user_config[CONF_USERNAME], user_config[CONF_PASSWORD])
    try:
        await auth.authenticate()
    except AuthenticationError as exc:
        raise ConfigEntryAuthFailed from exc
    except AquariteError as exc:
        raise ConfigEntryNotReady from exc

    api = AquariteClient(auth)
    try:
        pools = await api.get_pools()
    except AquariteError as exc:
        raise ConfigEntryNotReady from exc

    if not pools:
        raise ConfigEntryNotReady("No pools found for this account")

    data = AquariteData(auth=auth, api=api)

    for pool_id, pool_name in pools.items():
        coordinator = AquariteDataUpdateCoordinator(
            hass, entry, auth, api, pool_id, pool_name
        )
        await coordinator.async_config_entry_first_refresh()
        try:
            await coordinator.subscribe()
        except AquariteError as exc:
            raise ConfigEntryNotReady from exc
        data.coordinators[pool_id] = coordinator

    # Start shared background tasks (one per account, shared across pools)
    data.token_task = hass.async_create_background_task(
        _token_refresh_loop(hass, data), "Aquarite token refresh"
    )
    data.health_task = hass.async_create_background_task(
        _periodic_health_check(hass, data), "Aquarite health check"
    )

    entry.runtime_data = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AquariteConfigEntry) -> bool:
    """Unload Aquarite config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unloaded:
        data = entry.runtime_data
        # Cancel shared tasks first (stop sources of resubscription)
        for task in (data.health_task, data.token_task):
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        # Then shut down per-pool coordinators
        for coordinator in data.coordinators.values():
            await coordinator.async_shutdown()

    return unloaded


async def _token_refresh_loop(hass: HomeAssistant, data: AquariteData) -> None:
    """Maintain token validity; refresh all pool subscriptions on renewal."""
    retry_delay = 10
    while not hass.is_stopping:
        try:
            if data.auth.is_token_expiring():
                _LOGGER.debug("Token expiring soon, refreshing")
                _, refreshed = await data.auth.get_client()
                if refreshed:
                    for coordinator in data.coordinators.values():
                        await coordinator.refresh_subscription()
            retry_delay = 10
            sleep_time = data.auth.calculate_sleep_duration()
            await asyncio.sleep(sleep_time)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Error maintaining token: %s. Retrying in %ss", err, retry_delay
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 600)


async def _periodic_health_check(hass: HomeAssistant, data: AquariteData) -> None:
    """Monitor connection; resubscribe all pools on error."""
    while not hass.is_stopping:
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
        try:
            await data.auth.get_client()
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Health check failed, resubscribing: %s", err)
            for coordinator in data.coordinators.values():
                await coordinator.refresh_subscription()
