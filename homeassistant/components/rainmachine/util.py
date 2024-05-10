"""Define RainMachine utilities."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER

SIGNAL_REBOOT_COMPLETED = "rainmachine_reboot_completed_{0}"
SIGNAL_REBOOT_REQUESTED = "rainmachine_reboot_requested_{0}"


class RunStates(StrEnum):
    """Define an enum for program/zone run states."""

    NOT_RUNNING = "Not Running"
    QUEUED = "Queued"
    RUNNING = "Running"


RUN_STATE_MAP = {
    0: RunStates.NOT_RUNNING,
    1: RunStates.RUNNING,
    2: RunStates.QUEUED,
}


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
    ent_reg = er.async_get(hass)
    for strategy in entity_replacement_strategies:
        try:
            [registry_entry] = [
                registry_entry
                for registry_entry in ent_reg.entities.get_entries_for_config_entry_id(
                    entry.entry_id
                )
                if registry_entry.domain == strategy.old_domain
                and registry_entry.unique_id == strategy.old_unique_id
            ]
        except ValueError:
            continue

        old_entity_id = registry_entry.entity_id
        if strategy.remove_old_entity:
            LOGGER.info('Removing old entity: "%s"', old_entity_id)
            ent_reg.async_remove(old_entity_id)


def key_exists(data: dict[str, Any], search_key: str) -> bool:
    """Return whether a key exists in a nested dict."""
    for key, value in data.items():
        if key == search_key:
            return True
        if isinstance(value, dict):
            return key_exists(value, search_key)
    return False


class RainMachineDataUpdateCoordinator(DataUpdateCoordinator[dict]):  # pylint: disable=hass-enforce-coordinator-module
    """Define an extended DataUpdateCoordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: ConfigEntry,
        name: str,
        api_category: str,
        update_interval: timedelta,
        update_method: Callable[..., Awaitable],
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            name=name,
            update_interval=update_interval,
            update_method=update_method,
            always_update=False,
        )

        self._rebooting = False
        self._signal_handler_unsubs: list[Callable[..., None]] = []
        self.config_entry = entry
        self.signal_reboot_completed = SIGNAL_REBOOT_COMPLETED.format(
            self.config_entry.entry_id
        )
        self.signal_reboot_requested = SIGNAL_REBOOT_REQUESTED.format(
            self.config_entry.entry_id
        )

    @callback
    def async_initialize(self) -> None:
        """Initialize the coordinator."""

        @callback
        def async_reboot_completed() -> None:
            """Respond to a reboot completed notification."""
            LOGGER.debug("%s responding to reboot complete", self.name)
            self._rebooting = False
            self.last_update_success = True
            self.async_update_listeners()

        @callback
        def async_reboot_requested() -> None:
            """Respond to a reboot request."""
            LOGGER.debug("%s responding to reboot request", self.name)
            self._rebooting = True
            self.last_update_success = False
            self.async_update_listeners()

        for signal, func in (
            (self.signal_reboot_completed, async_reboot_completed),
            (self.signal_reboot_requested, async_reboot_requested),
        ):
            self._signal_handler_unsubs.append(
                async_dispatcher_connect(self.hass, signal, func)
            )

        @callback
        def async_check_reboot_complete() -> None:
            """Check whether an active reboot has been completed."""
            if self._rebooting and self.last_update_success:
                LOGGER.debug("%s discovered reboot complete", self.name)
                async_dispatcher_send(self.hass, self.signal_reboot_completed)

        self.async_add_listener(async_check_reboot_complete)

        @callback
        def async_teardown() -> None:
            """Tear the coordinator down appropriately."""
            for unsub in self._signal_handler_unsubs:
                unsub()

        self.config_entry.async_on_unload(async_teardown)
