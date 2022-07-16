"""Update entities for Ubiquiti network devices."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.update import (
    DOMAIN,
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_MANUFACTURER, DOMAIN as UNIFI_DOMAIN
from .unifi_entity_base import UniFiBase

LOGGER = logging.getLogger(__name__)

DEVICE_UPDATE = "device_update"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up update entities for UniFi Network integration."""
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    controller.entities[DOMAIN] = {DEVICE_UPDATE: set()}

    @callback
    def items_added(
        clients: set = controller.api.clients, devices: set = controller.api.devices
    ) -> None:
        """Add device update entities."""
        add_device_update_entities(controller, async_add_entities, devices)

    for signal in (controller.signal_update, controller.signal_options_update):
        config_entry.async_on_unload(
            async_dispatcher_connect(hass, signal, items_added)
        )

    items_added()


@callback
def add_device_update_entities(controller, async_add_entities, devices):
    """Add new device update entities from the controller."""
    entities = []

    for mac in devices:
        if mac in controller.entities[DOMAIN][UniFiDeviceUpdateEntity.TYPE]:
            continue

        device = controller.api.devices[mac]
        entities.append(UniFiDeviceUpdateEntity(device, controller))

    if entities:
        async_add_entities(entities)


class UniFiDeviceUpdateEntity(UniFiBase, UpdateEntity):
    """Update entity for a UniFi network infrastructure device."""

    DOMAIN = DOMAIN
    TYPE = DEVICE_UPDATE
    _attr_device_class = UpdateDeviceClass.FIRMWARE

    def __init__(self, device, controller):
        """Set up device update entity."""
        super().__init__(device, controller)

        self.device = self._item

        self._attr_supported_features = UpdateEntityFeature.PROGRESS

        if self.controller.site_role == "admin":
            self._attr_supported_features |= UpdateEntityFeature.INSTALL

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.device.name or self.device.model

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return f"{self.TYPE}-{self.device.mac}"

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return not self.device.disabled and self.controller.available

    @property
    def in_progress(self) -> bool:
        """Update installation in progress."""
        return self.device.state == 4

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return self.device.version

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self.device.upgrade_to_firmware or self.device.version

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self.device.mac)},
            manufacturer=ATTR_MANUFACTURER,
            model=self.device.model,
            sw_version=self.device.version,
        )

        if self.device.name:
            info[ATTR_NAME] = self.device.name

        return info

    async def options_updated(self) -> None:
        """No action needed."""

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await self.controller.api.devices.upgrade(self.device.mac)
