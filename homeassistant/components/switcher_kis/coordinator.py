"""Coordinator for the Switcher integration."""

import asyncio
from datetime import timedelta
import logging
from typing import override

from aioswitcher.api import SwitcherApi
from aioswitcher.device import DeviceCategory, SwitcherBase

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, update_coordinator
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, MAX_UPDATE_INTERVAL_SEC, POLL_TIMEOUT_SEC, SIGNAL_DEVICE_ADD

_LOGGER = logging.getLogger(__name__)


class SwitcherDataUpdateCoordinator(
    update_coordinator.DataUpdateCoordinator[SwitcherBase]
):
    """Switcher device data update coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: SwitcherBase,
    ) -> None:
        """Initialize the Switcher device coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=device.name,
            update_interval=timedelta(seconds=MAX_UPDATE_INTERVAL_SEC),
        )
        self.data = device
        self.token = entry.data.get(CONF_TOKEN)

    @override
    async def _async_update_data(self) -> SwitcherBase:
        """Poll the device when broadcasts stop before marking it unavailable.

        This is only reached when no broadcast has arrived for
        ``MAX_UPDATE_INTERVAL_SEC``. Rather than declaring the device dead on a
        lost broadcast alone, probe it over TCP. If it answers it stays
        available (the next broadcast refreshes the live state); if it does not,
        it is marked unavailable while the listener keeps waiting for it to come
        back on its own.
        """
        device = self.data
        try:
            async with asyncio.timeout(POLL_TIMEOUT_SEC):
                await self._async_probe(device)
        except (TimeoutError, OSError, RuntimeError) as err:
            raise update_coordinator.UpdateFailed(
                f"Device {self.name} did not send an update for"
                f" {MAX_UPDATE_INTERVAL_SEC} seconds and did not answer a poll:"
                f" {err}"
            ) from err

        _LOGGER.debug(
            "Device %s missed broadcasts but answered a poll, keeping it available",
            self.name,
        )
        # Return the coordinator's current data rather than the pre-probe
        # snapshot: a broadcast that arrived during the probe already refreshed
        # self.data, and returning it avoids reverting to a stale device.
        return self.data

    async def _async_probe(self, device: SwitcherBase) -> None:
        """Open a TCP session to the device and read its state as a liveness check."""
        category = device.device_type.category
        async with SwitcherApi(
            device.device_type,
            device.ip_address,
            device.device_id,
            device.device_key,
            self.token,
        ) as api:
            if category is DeviceCategory.THERMOSTAT:
                await api.get_breeze_state()
            elif category in (
                DeviceCategory.SHUTTER,
                DeviceCategory.SINGLE_SHUTTER_DUAL_LIGHT,
                DeviceCategory.DUAL_SHUTTER_SINGLE_LIGHT,
            ):
                await api.get_shutter_state()
            elif category is DeviceCategory.LIGHT:
                await api.get_light_state()
            elif category is DeviceCategory.HEATER:
                await api.get_heater_state()
            else:
                await api.get_state()

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
            config_entry_id=self.config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, self.mac_address)},
            identifiers={(DOMAIN, self.device_id)},
            manufacturer="Switcher",
            name=self.name,
            model=self.model,
        )
        async_dispatcher_send(self.hass, SIGNAL_DEVICE_ADD, self)
