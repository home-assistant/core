"""Firmware update platform for tplink."""
from __future__ import annotations

import asyncio
from typing import Any, cast

from kasa import Device

# TODO: Firmware should be pulled up for all supported devices
from kasa.smart.modules.firmware import Firmware

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import legacy_device_id
from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity
from .models import TPLinkData

FAKE_INSTALL_SLEEP_TIME = 0.5


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up demo update platform."""
    data: TPLinkData = hass.data[DOMAIN][config_entry.entry_id]
    parent_coordinator = data.parent_coordinator
    device = cast(Device, parent_coordinator.device)
    entities: list = []

    def _create_entities(dev):
        entities = []
        if "Firmware" in device.modules:
            entities.append(Update(device, parent_coordinator, parent=dev))

        return entities

    for child in device.children:
        entities.extend(_create_entities(child))

    entities.extend(_create_entities(device))

    async_add_entities(entities)


async def _fake_install() -> None:
    """Fake install an update."""
    await asyncio.sleep(FAKE_INSTALL_SLEEP_TIME)


class Update(CoordinatedTPLinkEntity, UpdateEntity):
    """Representation of a demo update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_name = "Update"
    _attr_should_poll = False

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        parent: Device = None,
    ) -> None:
        """Initialize the Demo select entity."""
        super().__init__(device, coordinator, parent)

        self._attr_unique_id = f"{legacy_device_id(device)}_update"
        self._attr_supported_features |= UpdateEntityFeature.INSTALL
        # TODO: Maybe in the future
        # self._attr_supported_features |= UpdateEntityFeature.PROGRESS

        self._update_module: Firmware = device.modules["Firmware"]

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_installed_version = self._update_module.current_firmware
        # self._attr_device_class = device_class  # TODO: separate handling for subdevices?
        self._attr_latest_version = self._update_module.latest_firmware
        self._attr_release_summary = (
            self._update_module.firmware_update_info.release_notes
        )
        self._attr_is_on = self._update_module.update_available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        self._attr_in_progress = True
        # TODO: allow passing an awaitable for updates
        #  the awaitable should update _attr_in_progress and call async_write_ha_state
        await self._update_module.update()

        self._attr_in_progress = False
        self.async_write_ha_state()
