"""Support for Songpal-enabled (Sony) media devices."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from songpal import (
    ConnectChange,
    ContentChange,
    Device,
    PowerChange,
    SettingChange,
    SongpalException,
    VolumeChange,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .device import device_info, device_unique_id

_LOGGER = logging.getLogger(__name__)

PARAM_NAME = "name"
PARAM_VALUE = "value"

INITIAL_RETRY_DELAY = 10


class SongpalCoordinator(DataUpdateCoordinator):
    """Coordinator to manage a Songpal device."""

    device_name: str
    _endpoint: str
    device: Device
    available: bool
    data: dict[str, Any]
    initialized: bool = False

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, name: str, device: Device
    ) -> None:
        """Initialize coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            update_method=self.update,
            update_interval=timedelta(seconds=10),
        )

        self.device_name = name
        self.data = {}
        self.device = device
        self._initialized = False

    async def _async_setup(self):
        await self.async_activate_websocket()
        await self.full_refresh()
        self.async_set_updated_data(self.data)

    async def update(
        self,
        log_failures=True,
        raise_on_auth_failed=False,
        scheduled=False,
        raise_on_entry_error=False,
    ):
        """Poll for data updates that are not pushed."""
        self.data = await self.polling_refresh(self.data)
        return self.data

    async def async_shutdown(self) -> None:
        """Run when entity will be removed from hass."""
        await self.device.stop_listen_notifications()
        await super().async_shutdown()

    async def async_activate_websocket(self):
        """Activate websocket for listening if wanted."""
        _LOGGER.warning("Activating websocket connection")

        async def _volume_changed(volume: VolumeChange):
            _LOGGER.debug("Volume changed: %s", volume)

            self.data["volumes"] = await self.device.get_volume_information()
            self.async_set_updated_data(self.data)

        async def _source_changed(content: ContentChange):
            _LOGGER.debug("Source changed: %s", content)

            self.data["inputs"] = await self.device.get_inputs()
            self.async_set_updated_data(self.data)

        async def _setting_changed(setting: SettingChange):
            _LOGGER.debug("Setting changed: %s", setting)

            data = self.data
            data["sound_settings"] = await self.device.get_sound_settings()
            data["bluetooth_settings"] = await self.device.get_bluetooth_settings()
            data["misc_settings"] = await self.device.get_misc_settings()
            data["playback_settings"] = await self.device.get_playback_settings()
            self.data = data
            self.async_set_updated_data(self.data)

        async def _power_changed(power: PowerChange):
            _LOGGER.debug("Power changed: %s", power)

            self.data["power"] = await self.device.get_power()
            self.async_set_updated_data(self.data)

        async def _try_reconnect(connect: ConnectChange):
            _LOGGER.warning(
                "[%s(%s)] Got disconnected, trying to reconnect",
                self.name,
                self.device.endpoint,
            )
            _LOGGER.debug("Disconnected: %s", connect.exception)
            self.available = False
            self.async_set_updated_data(self.data)

            # Try to reconnect forever, a successful reconnect will initialize
            # the websocket connection again.
            delay = INITIAL_RETRY_DELAY
            while not self.available:
                _LOGGER.debug("Trying to reconnect in %s seconds", delay)
                await asyncio.sleep(delay)

                try:
                    await self.device.get_supported_methods()
                except SongpalException as ex:
                    _LOGGER.debug("Failed to reconnect: %s", ex)
                    delay = min(2 * delay, 300)
                else:
                    # We need to inform HA about the state in case we are coming
                    # back from a disconnected state.
                    await self.full_refresh()
                    self.async_set_updated_data(self.data)

            self.hass.loop.create_task(self.device.listen_notifications())
            _LOGGER.warning(
                "[%s(%s)] Connection reestablished", self.name, self.device.endpoint
            )

        self.device.on_notification(VolumeChange, _volume_changed)
        self.device.on_notification(ContentChange, _source_changed)
        self.device.on_notification(PowerChange, _power_changed)
        self.device.on_notification(SettingChange, _setting_changed)
        self.device.on_notification(ConnectChange, _try_reconnect)

        async def handle_stop(event):
            await self.device.stop_listen_notifications()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_stop)

        self.hass.loop.create_task(self.device.listen_notifications())

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{DOMAIN}-{device_unique_id(self.data)}-coordinator"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return device_info(self.device_name, self.data)

    async def async_set_sound_setting(self, name, value):
        """Change a setting on the device."""
        _LOGGER.debug("Calling set_sound_setting with %s: %s", name, value)
        await self.device.set_sound_settings(name, value)

    async def polling_refresh(self, data: dict[str, Any]) -> dict[str, Any]:
        """Fetch non-pushed updates from the device."""
        try:
            data["sound_settings"] = await self.device.get_sound_settings()
            data["bluetooth_settings"] = await self.device.get_bluetooth_settings()
            data["misc_settings"] = await self.device.get_misc_settings()
            data["playback_settings"] = await self.device.get_playback_settings()
            data["eq"] = await self.device.get_custom_eq()
            data["play_info"] = await self.device.get_play_info()
        except SongpalException as ex:
            _LOGGER.error("Unable to refresh songpal state: %s", ex)
            self.available = False

        return data

    async def full_refresh(self) -> dict[str, Any]:
        """Fetch full state from the device."""
        try:
            data = self.data

            if "sysinfo" not in data:
                data["sysinfo"] = await self.device.get_system_info()

            if "interface_info" not in data:
                data["interface_info"] = await self.device.get_interface_information()

            volumes = await self.device.get_volume_information()
            if not volumes:
                _LOGGER.error("Got no volume controls, bailing out")
                self.available = False
                return data
            data["volumes"] = volumes

            data["power"] = await self.device.get_power()
            _LOGGER.debug("Got state: %s", data["power"].status)

            data["inputs"] = await self.device.get_inputs()
            _LOGGER.debug("Got ins: %s", data["inputs"])

            data = await self.polling_refresh(data)

            self.data = data
            self.available = True
            self.initialized = True

        except SongpalException as ex:
            _LOGGER.error("Unable to refresh songpal state: %s", ex)
            self.available = False

        return data
