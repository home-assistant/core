"""Coordinator for Arcam FMJ integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from arcam.fmj import ConnectionFailed
from arcam.fmj.client import Client
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
        self.last_update_success = False

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
            await self.state.update()
        except ConnectionFailed as err:
            raise UpdateFailed(
                f"Connection failed during update for zone {self.state.zn}"
            ) from err

    @callback
    def async_notify_data_updated(self) -> None:
        """Notify that new data has been received from the device."""
        self.async_set_updated_data(None)

    @callback
    def async_notify_connected(self) -> None:
        """Handle client connected."""
        self.hass.async_create_task(self.async_refresh())

    @callback
    def async_notify_disconnected(self) -> None:
        """Handle client disconnected."""
        self.last_update_success = False
        self.async_update_listeners()
