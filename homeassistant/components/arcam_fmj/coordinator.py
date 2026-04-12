"""Coordinator for Arcam FMJ integration."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging

from arcam.fmj import ConnectionFailed
from arcam.fmj.client import AmxDuetResponse, Client, ResponsePacket
from arcam.fmj.state import State

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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

        name = config_entry.title
        unique_id = config_entry.unique_id or config_entry.entry_id
        unique_id_device = unique_id
        if zone != 1:
            unique_id_device += f"-{zone}"
            name += f" Zone {zone}"

        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id_device)},
            manufacturer="Arcam",
            model="Arcam FMJ AVR",
            name=name,
        )
        self.zone_unique_id = f"{unique_id}-{zone}"

        if zone != 1:
            self.device_info["via_device"] = (DOMAIN, unique_id)

    async def _async_update_data(self) -> None:
        """Fetch data for manual refresh."""
        try:
            self.update_in_progress = True
            await self.state.update()
        except ConnectionFailed as err:
            raise UpdateFailed(
                f"Connection failed during update for zone {self.state.zn}"
            ) from err
        finally:
            self.update_in_progress = False

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
