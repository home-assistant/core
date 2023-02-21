"""The Nibe Heat Pump integration."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import timedelta
from functools import cached_property
from typing import Any, Generic, TypeVar

from nibe.coil import Coil
from nibe.connection import Connection
from nibe.connection.modbus import Modbus
from nibe.connection.nibegw import NibeGW, ProductInfo
from nibe.exceptions import CoilNotFoundException, CoilReadException
from nibe.heatpump import HeatPump, Model, Series

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_MODEL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_CONNECTION_TYPE,
    CONF_CONNECTION_TYPE_MODBUS,
    CONF_CONNECTION_TYPE_NIBEGW,
    CONF_LISTENING_PORT,
    CONF_MODBUS_UNIT,
    CONF_MODBUS_URL,
    CONF_REMOTE_READ_PORT,
    CONF_REMOTE_WRITE_PORT,
    CONF_WORD_SWAP,
    DOMAIN,
    LOGGER,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]
COIL_READ_RETRIES = 5


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nibe Heat Pump from a config entry."""

    heatpump = HeatPump(Model[entry.data[CONF_MODEL]])
    await heatpump.initialize()

    connection: Connection
    connection_type = entry.data[CONF_CONNECTION_TYPE]

    if connection_type == CONF_CONNECTION_TYPE_NIBEGW:
        heatpump.word_swap = entry.data[CONF_WORD_SWAP]
        connection = NibeGW(
            heatpump,
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_REMOTE_READ_PORT],
            entry.data[CONF_REMOTE_WRITE_PORT],
            listening_port=entry.data[CONF_LISTENING_PORT],
        )
    elif connection_type == CONF_CONNECTION_TYPE_MODBUS:
        connection = Modbus(
            heatpump, entry.data[CONF_MODBUS_URL], entry.data[CONF_MODBUS_UNIT]
        )
    else:
        raise HomeAssistantError(f"Connection type {connection_type} is not supported.")

    await connection.start()

    assert heatpump.model

    async def _async_stop(_):
        await connection.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )

    coordinator = Coordinator(hass, heatpump, connection)

    data = hass.data.setdefault(DOMAIN, {})
    data[entry.entry_id] = coordinator

    reg = dr.async_get(hass)
    device_entry = reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        manufacturer="NIBE Energy Systems",
        name=heatpump.model.name,
    )

    def _on_product_info(product_info: ProductInfo):
        reg.async_update_device(
            device_id=device_entry.id,
            model=product_info.model,
            sw_version=str(product_info.firmware_version),
        )

    if hasattr(connection, "PRODUCT_INFO_EVENT") and hasattr(connection, "subscribe"):
        connection.subscribe(connection.PRODUCT_INFO_EVENT, _on_product_info)
    else:
        reg.async_update_device(device_id=device_entry.id, model=heatpump.model.name)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Trigger a refresh again now that all platforms have registered
    hass.async_create_task(coordinator.async_refresh())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: Coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unload_ok


_DataTypeT = TypeVar("_DataTypeT")
_ContextTypeT = TypeVar("_ContextTypeT")


class ContextCoordinator(
    Generic[_DataTypeT, _ContextTypeT], DataUpdateCoordinator[_DataTypeT]
):
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


class Coordinator(ContextCoordinator[dict[int, Coil], int]):
    """Update coordinator for nibe heat pumps."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        heatpump: HeatPump,
        connection: Connection,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass, LOGGER, name="Nibe Heat Pump", update_interval=timedelta(seconds=60)
        )

        self.data = {}
        self.seed: dict[int, Coil] = {}
        self.connection = connection
        self.heatpump = heatpump
        self.task: asyncio.Task | None = None

        heatpump.subscribe(heatpump.COIL_UPDATE_EVENT, self._on_coil_update)

    def _on_coil_update(self, coil: Coil):
        """Handle callback on coil updates."""
        self.data[coil.address] = coil
        self.seed[coil.address] = coil
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

    def get_coil_value(self, coil: Coil) -> int | str | float | None:
        """Return a coil with data and check for validity."""
        if coil_with_data := self.data.get(coil.address):
            return coil_with_data.value
        return None

    def get_coil_float(self, coil: Coil) -> float | None:
        """Return a coil with float and check for validity."""
        if value := self.get_coil_value(coil):
            return float(value)
        return None

    async def async_write_coil(self, coil: Coil, value: int | float | str) -> None:
        """Write coil and update state."""
        coil.value = value
        coil = await self.connection.write_coil(coil)

        self.data[coil.address] = coil

        self.async_update_context_listeners([coil.address])

    async def async_read_coil(self, coil: Coil) -> Coil:
        """Read coil and update state using callbacks."""
        return await self.connection.read_coil(coil)

    async def _async_update_data(self) -> dict[int, Coil]:
        self.task = asyncio.current_task()
        try:
            return await self._async_update_data_internal()
        finally:
            self.task = None

    async def _async_update_data_internal(self) -> dict[int, Coil]:
        result: dict[int, Coil] = {}

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
            async for coil in self.connection.read_coils(_get_coils()):
                result[coil.address] = coil
                self.seed.pop(coil.address, None)
        except CoilReadException as exception:
            if not result:
                raise UpdateFailed(f"Failed to update: {exception}") from exception
            self.logger.debug(
                "Some coils failed to update, and may be unsupported: %s", exception
            )

        return result

    async def async_shutdown(self):
        """Make sure a coordinator is shut down as well as it's connection."""
        if self.task:
            self.task.cancel()
            await asyncio.wait((self.task,))
        self._unschedule_refresh()
        await self.connection.stop()


class CoilEntity(CoordinatorEntity[Coordinator]):
    """Base for coil based entities."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: Coordinator, coil: Coil, entity_format: str
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator, {coil.address})
        self.entity_id = async_generate_entity_id(
            entity_format, coil.name, hass=coordinator.hass
        )
        self._attr_name = coil.title
        self._attr_unique_id = f"{coordinator.unique_id}-{coil.address}"
        self._attr_device_info = coordinator.device_info
        self._coil = coil

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._coil.address in (
            self.coordinator.data or {}
        )

    def _async_read_coil(self, coil: Coil):
        """Update state of entity based on coil data."""

    async def _async_write_coil(self, value: int | float | str):
        """Write coil and update state."""
        await self.coordinator.async_write_coil(self._coil, value)

    def _handle_coordinator_update(self) -> None:
        coil = self.coordinator.data.get(self._coil.address)
        if coil is None:
            return

        self._coil = coil
        self._async_read_coil(coil)
        self.async_write_ha_state()
