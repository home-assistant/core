"""Coordinator for Arcam FMJ integration."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging
from typing import override

from arcam.fmj.client import AmxDuetResponse, Client, ResponsePacket
from arcam.fmj.errors import ConnectionFailed
from arcam.fmj.state import State

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class ArcamFmjRuntimeData:
    """Runtime data for Arcam FMJ integration."""

    client: Client
    coordinators: dict[int, ArcamFmjCoordinator]


type ArcamFmjConfigEntry = ConfigEntry[ArcamFmjRuntimeData]


class ArcamFmjCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for a single Arcam FMJ zone."""

    config_entry: ArcamFmjConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ArcamFmjConfigEntry,
        client: Client,
        zone: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Arcam FMJ zone {zone}",
        )
        self.client = client
        self.state = State(client, zone)
        self.update_in_progress = False

        device_name = config_entry.title
        unique_id = config_entry.unique_id or config_entry.entry_id
        unique_id_device = unique_id
        if zone != 1:
            unique_id_device += f"-{zone}"
            device_name += f" Zone {zone}"

        self._device_identifier = (DOMAIN, unique_id_device)
        self.device_name = device_name
        self.device_info = DeviceInfo(
            identifiers={self._device_identifier},
            manufacturer="Arcam",
            model=self.state.model or "Arcam FMJ AVR",
            name=device_name,
            sw_version=self.state.revision,
        )
        self.zone_unique_id = f"{unique_id}-{zone}"

    @override
    async def _async_update_data(self) -> None:
        """Fetch data for manual refresh."""
        try:
            self.update_in_progress = True
            await self.state.update()
            self._update_device_registry()
        except ConnectionFailed as err:
            raise UpdateFailed(
                f"Connection failed during update for zone {self.state.zn}"
            ) from err
        finally:
            self.update_in_progress = False

    @callback
    def _update_device_registry(self) -> None:
        """Update the device registry with discovered device information."""
        model = self.state.model
        software_version = self.state.revision
        if model is None and software_version is None:
            return

        if model is not None:
            self.device_info["model"] = model
        if software_version is not None:
            self.device_info["sw_version"] = software_version

        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device_by_identifier(
            self._device_identifier, self.config_entry.entry_id
        )
        if device is None:
            return

        updates: dict[str, str] = {}
        if model is not None and device.model != model:
            updates["model"] = model
        if software_version is not None and device.sw_version != software_version:
            updates["sw_version"] = software_version
        if updates:
            device_registry.async_update_device(device.id, **updates)

    @callback
    def _async_notify_packet(self, packet: ResponsePacket | AmxDuetResponse) -> None:
        """Packet callback to detect changes to state."""
        if (
            not isinstance(packet, ResponsePacket)
            or packet.zn != self.state.zn
            or self.update_in_progress
        ):
            return

        self.async_update_listeners()

    @asynccontextmanager
    async def async_monitor_client(self) -> AsyncGenerator[None]:
        """Monitor a client and state for changes while connected."""
        async with self.state:
            self.hass.async_create_task(self.async_refresh())
            try:
                with self.client.listen(self._async_notify_packet):
                    yield
            finally:
                self.hass.async_create_task(self.async_refresh())
