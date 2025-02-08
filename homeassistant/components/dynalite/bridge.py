"""Code to handle a Dynalite bridge."""

from __future__ import annotations

from collections.abc import Callable
from types import MappingProxyType
from typing import Any

from dynalite_devices_lib.dynalite_devices import (
    CONF_AREA as dyn_CONF_AREA,
    CONF_PRESET as dyn_CONF_PRESET,
    NOTIFICATION_PACKET,
    NOTIFICATION_PRESET,
    DynaliteBaseDevice,
    DynaliteDevices,
    DynaliteNotification,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import ATTR_AREA, ATTR_HOST, ATTR_PACKET, ATTR_PRESET, LOGGER, PLATFORMS
from .convert_config import convert_config

type DynaliteConfigEntry = ConfigEntry[DynaliteBridge]


class DynaliteBridge:
    """Manages a single Dynalite bridge."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the system based on host parameter."""
        self.hass = hass
        self.async_add_devices: dict[str, Callable] = {}
        self.waiting_devices: dict[str, list[str]] = {}
        self.host = config[CONF_HOST]
        # Configure the dynalite devices
        self.dynalite_devices = DynaliteDevices(
            new_device_func=self.add_devices_when_registered,
            update_device_func=self.update_device,
            notification_func=self.handle_notification,
        )
        self.dynalite_devices.configure(config)

    async def async_setup(self) -> bool:
        """Set up a Dynalite bridge."""
        # Configure the dynalite devices
        LOGGER.debug("Setting up bridge - host %s", self.host)
        return await self.dynalite_devices.async_setup()

    def reload_config(self, config: MappingProxyType[str, Any]) -> None:
        """Reconfigure a bridge when config changes."""
        LOGGER.debug("Reloading bridge - host %s, config %s", self.host, config)
        self.dynalite_devices.configure(convert_config(config))

    def update_signal(self, device: DynaliteBaseDevice | None = None) -> str:
        """Create signal to use to trigger entity update."""
        if device:
            signal = f"dynalite-update-{self.host}-{device.unique_id}"
        else:
            signal = f"dynalite-update-{self.host}"
        return signal

    @callback
    def update_device(self, device: DynaliteBaseDevice | None = None) -> None:
        """Call when a device or all devices should be updated."""
        if not device:
            # This is used to signal connection or disconnection, so all devices may become available or not.
            log_string = (
                "Connected" if self.dynalite_devices.connected else "Disconnected"
            )
            LOGGER.debug("%s to dynalite host", log_string)
            async_dispatcher_send(self.hass, self.update_signal())
        else:
            async_dispatcher_send(self.hass, self.update_signal(device))

    @callback
    def handle_notification(self, notification: DynaliteNotification) -> None:
        """Handle a notification from the platform and issue events."""
        if notification.notification == NOTIFICATION_PACKET:
            self.hass.bus.async_fire(
                "dynalite_packet",
                {
                    ATTR_HOST: self.host,
                    ATTR_PACKET: notification.data[NOTIFICATION_PACKET],
                },
            )
        if notification.notification == NOTIFICATION_PRESET:
            self.hass.bus.async_fire(
                "dynalite_preset",
                {
                    ATTR_HOST: self.host,
                    ATTR_AREA: notification.data[dyn_CONF_AREA],
                    ATTR_PRESET: notification.data[dyn_CONF_PRESET],
                },
            )

    @callback
    def register_add_devices(self, platform: str, async_add_devices: Callable) -> None:
        """Add an async_add_entities for a category."""
        self.async_add_devices[platform] = async_add_devices
        if platform in self.waiting_devices:
            self.async_add_devices[platform](self.waiting_devices[platform])

    def add_devices_when_registered(self, devices: list[DynaliteBaseDevice]) -> None:
        """Add the devices to HA if the add devices callback was registered, otherwise queue until it is."""
        for platform in PLATFORMS:
            platform_devices = [
                device for device in devices if device.category == platform
            ]
            if platform in self.async_add_devices:
                self.async_add_devices[platform](platform_devices)
            else:  # handle it later when it is registered
                if platform not in self.waiting_devices:
                    self.waiting_devices[platform] = []
                self.waiting_devices[platform].extend(platform_devices)
