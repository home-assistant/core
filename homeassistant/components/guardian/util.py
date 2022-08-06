"""Define Guardian-specific utilities."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any, cast

from aioguardian import Client
from aioguardian.errors import GuardianError

from homeassistant.components.repairs import IssueSeverity, async_create_issue
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=30)

SIGNAL_REBOOT_REQUESTED = "guardian_reboot_requested_{0}"


@callback
def async_clean_up_old_entities(
    hass: HomeAssistant, entry: ConfigEntry, unique_id_suffixes_to_remove: tuple[str]
) -> None:
    """Clean up old, no-longer-used entities."""
    ent_reg = entity_registry.async_get(hass)
    for entity_registry_item in [
        e
        for e in ent_reg.entities.values()
        if e.config_entry_id == entry.entry_id
        and any(
            suffix
            for suffix in unique_id_suffixes_to_remove
            if e.unique_id.endswith(suffix)
        )
    ]:
        removed_entity_id = entity_registry_item.entity_id
        async_create_issue(
            hass,
            DOMAIN,
            f"removed_old_entity_{removed_entity_id}",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            translation_key="removed_old_entity",
            translation_placeholders={
                "removed_entity_id": removed_entity_id,
            },
        )
        LOGGER.debug('Removing old entity: "%s"', removed_entity_id)
        ent_reg.async_remove(removed_entity_id)


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
        self._signal_handler_unsubs: list[Callable[..., None]] = []

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

        self._signal_handler_unsubs.append(
            async_dispatcher_connect(
                self.hass, self.signal_reboot_requested, async_reboot_requested
            )
        )

        @callback
        def async_teardown() -> None:
            """Tear the coordinator down appropriately."""
            for unsub in self._signal_handler_unsubs:
                unsub()

        self.config_entry.async_on_unload(async_teardown)
