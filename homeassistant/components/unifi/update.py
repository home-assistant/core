"""Update entities for Ubiquiti network devices."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.models.device import DeviceUpgradeRequest

from homeassistant.components.update import (
    DOMAIN,
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_MANUFACTURER, DOMAIN as UNIFI_DOMAIN

if TYPE_CHECKING:
    from .controller import UniFiController

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
    def async_add_update_entity(_: ItemEvent, obj_id: str) -> None:
        """Add new device update entities from the controller."""
        async_add_entities([UnifiDeviceUpdateEntity(obj_id, controller)])

    controller.api.devices.subscribe(async_add_update_entity, ItemEvent.ADDED)

    for device_id in controller.api.devices:
        async_add_update_entity(ItemEvent.ADDED, device_id)


class UnifiDeviceUpdateEntity(UpdateEntity):
    """Update entity for a UniFi network infrastructure device."""

    DOMAIN = DOMAIN
    TYPE = DEVICE_UPDATE
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_has_entity_name = True

    def __init__(self, obj_id: str, controller: UniFiController) -> None:
        """Set up device update entity."""
        controller.entities[DOMAIN][DEVICE_UPDATE].add(obj_id)
        self.controller = controller
        self._obj_id = obj_id
        self._attr_unique_id = f"{self.TYPE}-{obj_id}"

        self._attr_supported_features = UpdateEntityFeature.PROGRESS
        if controller.site_role == "admin":
            self._attr_supported_features |= UpdateEntityFeature.INSTALL

        device = controller.api.devices[obj_id]
        self._attr_available = controller.available and not device.disabled
        self._attr_in_progress = device.state == 4
        self._attr_installed_version = device.version
        self._attr_latest_version = device.upgrade_to_firmware or device.version

        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, obj_id)},
            manufacturer=ATTR_MANUFACTURER,
            model=device.model,
            name=device.name or None,
            sw_version=device.version,
            hw_version=device.board_revision,
        )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        self.async_on_remove(
            self.controller.api.devices.subscribe(self.async_signalling_callback)
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal_reachable,
                self.async_signal_reachable_callback,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        self.controller.entities[DOMAIN][DEVICE_UPDATE].remove(self._obj_id)

    @callback
    def async_signalling_callback(self, event: ItemEvent, obj_id: str) -> None:
        """Object has new event."""
        device = self.controller.api.devices[self._obj_id]
        self._attr_available = self.controller.available and not device.disabled
        self._attr_in_progress = device.state == 4
        self._attr_installed_version = device.version
        self._attr_latest_version = device.upgrade_to_firmware or device.version
        self.async_write_ha_state()

    @callback
    def async_signal_reachable_callback(self) -> None:
        """Call when controller connection state change."""
        self.async_signalling_callback(ItemEvent.ADDED, self._obj_id)

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await self.controller.api.request(DeviceUpgradeRequest.create(self._obj_id))
