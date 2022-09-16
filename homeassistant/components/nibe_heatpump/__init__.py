"""The Nibe Heat Pump integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from nibe.coil import Coil
from nibe.connection import Connection
from nibe.connection.nibegw import NibeGW
from nibe.exceptions import CoilNotFoundException, CoilReadException
from nibe.heatpump import HeatPump, Model

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_MODEL, Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    CONF_CONNECTION_TYPE,
    CONF_CONNECTION_TYPE_NIBEGW,
    CONF_LISTENING_PORT,
    CONF_REMOTE_READ_PORT,
    CONF_REMOTE_WRITE_PORT,
    CONF_WORD_SWAP,
    DOMAIN,
)
from .utils import TooManyTriesException, retry

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nibe Heat Pump from a config entry."""

    heatpump = HeatPump(Model[entry.data[CONF_MODEL]])
    heatpump.word_swap = entry.data[CONF_WORD_SWAP]
    heatpump.initialize()

    connection_type = entry.data[CONF_CONNECTION_TYPE]

    if connection_type == CONF_CONNECTION_TYPE_NIBEGW:
        connection = NibeGW(
            heatpump,
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_REMOTE_READ_PORT],
            entry.data[CONF_REMOTE_WRITE_PORT],
            listening_port=entry.data[CONF_LISTENING_PORT],
        )
    else:
        raise HomeAssistantError(f"Connection type {connection_type} is not supported.")

    await connection.start()
    try:
        coordinator = Coordinator(hass, heatpump, connection)

        data = hass.data.setdefault(DOMAIN, {})
        data[entry.entry_id] = coordinator
        await coordinator.async_config_entry_first_refresh()

        reg = dr.async_get(hass)
        reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            manufacturer="NIBE Energy Systems",
            model=heatpump.model.name,
            name=heatpump.model.name,
        )

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    except Exception:
        await connection.stop()
        raise

    # Trigger a refresh again now that all platforms have registered
    hass.async_create_task(coordinator.async_refresh())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: Coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.connection.stop()

        # sleep a bit to make sure sockets are closed
        await asyncio.sleep(5)

    return unload_ok


class Coordinator(DataUpdateCoordinator[dict[int, Coil]]):
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
            hass, _LOGGER, name="Nibe Heat Pump", update_interval=timedelta(seconds=60)
        )

        self.connection = connection
        self.heatpump = heatpump

    @property
    def coils(self) -> dict[str, Coil]:
        """Return the full coil database."""
        return self.heatpump._address_to_coil  # pylint: disable=protected-access

    @property
    def unique_id(self) -> str:
        """Return unique id for this coordinator."""
        return self.config_entry.unique_id or self.config_entry.entry_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the main device."""
        return DeviceInfo(identifiers={(DOMAIN, self.unique_id)})

    def get_coil_data(self, coil: Coil | None) -> Coil | None:
        """Return a coil with data and check for validity."""
        if not self.data or not coil:
            return None

        coil = self.data.get(coil.address)
        if coil and coil.value != -3276.8:
            return coil
        return None

    def get_coil_value(self, coil: Coil | None) -> int | str | float | None:
        """Return a coil with data and check for validity."""
        if coil := self.get_coil_data(coil):
            return coil.value
        return None

    def get_coil_float(self, coil: Coil | None) -> float | None:
        """Return a coil with float and check for validity."""
        if value := self.get_coil_value(coil):
            return float(value)
        return None

    async def async_write_coil(
        self, coil: Coil | None, value: int | float | str
    ) -> None:
        """Write coil and update state."""
        if not coil:
            raise HomeAssistantError("No coil available")

        coil.value = value
        coil = await self.connection.write_coil(coil)

        if self.data:
            self.data[coil.address] = coil
            self.async_update_listeners()

    async def _async_update_data(self) -> dict[int, Coil]:
        @retry([0.0, 0.5], (CoilReadException))
        async def read_coil(coil: Coil):
            return await self.connection.read_coil(coil)

        callbacks: dict[int, list[CALLBACK_TYPE]] = {}
        for update_callback, context in list(self._listeners.values()):
            assert isinstance(context, set)
            for address in context:
                callbacks.setdefault(address, []).append(update_callback)

        result: dict[int, Coil] = {}

        if self.data is None:
            self.data = {}

        for address, callback_list in callbacks.items():
            try:
                coil = self.heatpump.get_coil_by_address(address)
                self.data[coil.address] = result[coil.address] = await read_coil(coil)
            except (CoilReadException, TooManyTriesException) as exception:
                self.logger.warning("Failed to update: %s", exception)
            except CoilNotFoundException as exception:
                self.logger.debug("Skipping missing coil: %s", exception)

            for update_callback in callback_list:
                update_callback()

        return result


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
        coil = self.coordinator.get_coil_data(self._coil)
        if coil is None:
            return

        self._coil = coil
        self._async_read_coil(coil)
        self.async_write_ha_state()
