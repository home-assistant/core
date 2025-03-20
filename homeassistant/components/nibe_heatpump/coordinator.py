"""The Nibe Heat Pump coordinator."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import date, timedelta
from typing import Any

from nibe.coil import Coil, CoilData
from nibe.connection import Connection
from nibe.exceptions import CoilNotFoundException, ReadException
from nibe.heatpump import HeatPump, Series
from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


class ContextCoordinator[_DataTypeT, _ContextTypeT](DataUpdateCoordinator[_DataTypeT]):
    """Update coordinator with context adjustments."""

    @cached_property
    def context_callbacks(self) -> dict[_ContextTypeT, list[CALLBACK_TYPE]]:
        """Return a dict of all callbacks registered for a given context."""
        callbacks: dict[_ContextTypeT, list[CALLBACK_TYPE]] = defaultdict(list)
        for update_callback, context in list(self._listeners.values()):
            assert isinstance(context, set)
            for address in context:
                callbacks[address].append(update_callback)
        return callbacks

    @callback
    def async_update_context_listeners(self, contexts: Iterable[_ContextTypeT]) -> None:
        """Update all listeners given a set of contexts."""
        update_callbacks: set[CALLBACK_TYPE] = set()
        for context in contexts:
            update_callbacks.update(self.context_callbacks.get(context, []))

        for update_callback in update_callbacks:
            update_callback()

    @callback
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        """Wrap standard function to prune cached callback database."""
        assert isinstance(context, set)
        context -= {None}
        release = super().async_add_listener(update_callback, context)
        self.__dict__.pop("context_callbacks", None)

        @callback
        def release_update():
            release()
            self.__dict__.pop("context_callbacks", None)

        return release_update


class CoilCoordinator(ContextCoordinator[dict[int, CoilData], int]):
    """Update coordinator for nibe heat pumps."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        heatpump: HeatPump,
        connection: Connection,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Nibe Heat Pump",
            update_interval=timedelta(seconds=60),
        )

        self.data = {}
        self.seed: dict[int, CoilData] = {}
        self.connection = connection
        self.heatpump = heatpump
        self.task: asyncio.Task | None = None

        heatpump.subscribe(heatpump.COIL_UPDATE_EVENT, self._on_coil_update)

    def _on_coil_update(self, data: CoilData):
        """Handle callback on coil updates."""
        coil = data.coil
        self.data[coil.address] = data
        self.seed[coil.address] = data
        self.async_update_context_listeners([coil.address])

    @property
    def series(self) -> Series:
        """Return which series of pump we are connected to."""
        return self.heatpump.series

    @property
    def coils(self) -> list[Coil]:
        """Return the full coil database."""
        return self.heatpump.get_coils()

    @property
    def unique_id(self) -> str:
        """Return unique id for this coordinator."""
        return self.config_entry.unique_id or self.config_entry.entry_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the main device."""
        return DeviceInfo(identifiers={(DOMAIN, self.unique_id)})

    def get_coil_value(self, coil: Coil) -> int | str | float | date | None:
        """Return a coil with data and check for validity."""
        if coil_with_data := self.data.get(coil.address):
            return coil_with_data.value
        return None

    def get_coil_float(self, coil: Coil) -> float | None:
        """Return a coil with float and check for validity."""
        if value := self.get_coil_value(coil):
            return float(value)  # type: ignore[arg-type]
        return None

    async def async_write_coil(self, coil: Coil, value: float | str) -> None:
        """Write coil and update state."""
        data = CoilData(coil, value)
        await self.connection.write_coil(data)

        self.data[coil.address] = data

        self.async_update_context_listeners([coil.address])

    async def async_read_coil(self, coil: Coil) -> CoilData:
        """Read coil and update state using callbacks."""
        return await self.connection.read_coil(coil)

    async def _async_update_data(self) -> dict[int, CoilData]:
        self.task = asyncio.current_task()
        try:
            return await self._async_update_data_internal()
        finally:
            self.task = None

    async def _async_update_data_internal(self) -> dict[int, CoilData]:
        result: dict[int, CoilData] = {}

        def _get_coils() -> Iterable[Coil]:
            for address in sorted(self.context_callbacks.keys()):
                if seed := self.seed.pop(address, None):
                    self.logger.debug("Skipping seeded coil: %d", address)
                    result[address] = seed
                    continue

                try:
                    coil = self.heatpump.get_coil_by_address(address)
                except CoilNotFoundException as exception:
                    self.logger.debug("Skipping missing coil: %s", exception)
                    continue
                yield coil

        try:
            async for data in self.connection.read_coils(_get_coils()):
                result[data.coil.address] = data
                self.seed.pop(data.coil.address, None)
        except ReadException as exception:
            if not result:
                raise UpdateFailed(f"Failed to update: {exception}") from exception
            self.logger.debug(
                "Some coils failed to update, and may be unsupported: %s", exception
            )

        return result

    async def async_shutdown(self):
        """Make sure a coordinator is shut down as well as it's connection."""
        await super().async_shutdown()
        if self.task:
            self.task.cancel()
            await asyncio.wait((self.task,))
        await self.connection.stop()
