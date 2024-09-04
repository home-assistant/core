"""Coordinator for the Switcher integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from aioswitcher.device import SwitcherBase

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, update_coordinator
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, MAX_UPDATE_INTERVAL_SEC, SIGNAL_DEVICE_ADD

_LOGGER = logging.getLogger(__name__)


class SwitcherDataUpdateCoordinator(
    update_coordinator.DataUpdateCoordinator[SwitcherBase]
):
    """Switcher device data update coordinator."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, device: SwitcherBase
    ) -> None:
        """Initialize the Switcher device coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=device.name,
            update_interval=timedelta(seconds=MAX_UPDATE_INTERVAL_SEC),
        )
        self.entry = entry
        self.data = device

    async def _async_update_data(self) -> SwitcherBase:
        """Mark device offline if no data."""
        raise update_coordinator.UpdateFailed(
            f"Device {self.name} did not send update for"
            f" {MAX_UPDATE_INTERVAL_SEC} seconds"
        )

    @property
    def model(self) -> str:
        """Switcher device model."""
        return self.data.device_type.value

    @property
    def device_id(self) -> str:
        """Switcher device id."""
        return self.data.device_id

    @property
    def mac_address(self) -> str:
        """Switcher device mac address."""
        return self.data.mac_address

    @callback
    def async_setup(self) -> None:
        """Set up the coordinator."""
        dev_reg = dr.async_get(self.hass)
        dev_reg.async_get_or_create(
            config_entry_id=self.entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, self.mac_address)},
            identifiers={(DOMAIN, self.device_id)},
            manufacturer="Switcher",
            name=self.name,
            model=self.model,
        )
        async_dispatcher_send(self.hass, SIGNAL_DEVICE_ADD, self)
