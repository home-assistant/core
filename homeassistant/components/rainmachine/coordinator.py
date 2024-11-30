"""Coordinator for the RainMachine integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER

SIGNAL_REBOOT_COMPLETED = "rainmachine_reboot_completed_{0}"
SIGNAL_REBOOT_REQUESTED = "rainmachine_reboot_requested_{0}"

if TYPE_CHECKING:
    from . import RainMachineConfigEntry


class RainMachineDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Define an extended DataUpdateCoordinator."""

    config_entry: RainMachineConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: RainMachineConfigEntry,
        name: str,
        api_category: str,
        update_interval: timedelta,
        update_method: Callable[[], Coroutine[Any, Any, dict]],
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
        self._signal_handler_unsubs: list[Callable[[], None]] = []
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
