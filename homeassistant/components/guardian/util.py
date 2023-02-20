"""Define Guardian-specific utilities."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, cast

from aioguardian import Client
from aioguardian.errors import GuardianError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=30)

SIGNAL_REBOOT_REQUESTED = "guardian_reboot_requested_{0}"


@dataclass
class EntityDomainReplacementStrategy:
    """Define an entity replacement."""

    old_domain: str
    old_unique_id: str
    replacement_entity_id: str
    breaks_in_ha_version: str
    remove_old_entity: bool = True


@callback
def async_finish_entity_domain_replacements(
    hass: HomeAssistant,
    entry: ConfigEntry,
    entity_replacement_strategies: Iterable[EntityDomainReplacementStrategy],
) -> None:
    """Remove old entities and create a repairs issue with info on their replacement."""
    ent_reg = entity_registry.async_get(hass)
    for strategy in entity_replacement_strategies:
        try:
            [registry_entry] = [
                registry_entry
                for registry_entry in ent_reg.entities.values()
                if registry_entry.config_entry_id == entry.entry_id
                and registry_entry.domain == strategy.old_domain
                and registry_entry.unique_id == strategy.old_unique_id
            ]
        except ValueError:
            continue

        old_entity_id = registry_entry.entity_id
        if strategy.remove_old_entity:
            LOGGER.info('Removing old entity: "%s"', old_entity_id)
            ent_reg.async_remove(old_entity_id)


class GuardianDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Define an extended DataUpdateCoordinator with some Guardian goodies."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: ConfigEntry,
        client: Client,
        api_name: str,
        api_coro: Callable[..., Awaitable],
        api_lock: asyncio.Lock,
        valve_controller_uid: str,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            name=f"{valve_controller_uid}_{api_name}",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )

        self._api_coro = api_coro
        self._api_lock = api_lock
        self._client = client

        self.config_entry = entry
        self.signal_reboot_requested = SIGNAL_REBOOT_REQUESTED.format(
            self.config_entry.entry_id
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Execute a "locked" API request against the valve controller."""
        async with self._api_lock, self._client:
            try:
                resp = await self._api_coro()
            except GuardianError as err:
                raise UpdateFailed(err) from err
        return cast(dict[str, Any], resp["data"])

    async def async_initialize(self) -> None:
        """Initialize the coordinator."""

        @callback
        def async_reboot_requested() -> None:
            """Respond to a reboot request."""
            self.last_update_success = False
            self.async_update_listeners()

        self.config_entry.async_on_unload(
            async_dispatcher_connect(
                self.hass, self.signal_reboot_requested, async_reboot_requested
            )
        )
