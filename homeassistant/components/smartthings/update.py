"""Support for update entities through the SmartThings cloud API."""

from __future__ import annotations

from typing import Any

from awesomeversion import AwesomeVersion, AwesomeVersionStrategy
from pysmartthings.models import Attribute, Capability, Command

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SmartThingsConfigEntry
from .entity import SmartThingsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add update entities for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsSwitch(entry_data.client, device, [Capability.FIRMWARE_UPDATE])
        for device in entry_data.devices.values()
        if Capability.FIRMWARE_UPDATE in device.status["main"]
    )


class SmartThingsSwitch(SmartThingsEntity, UpdateEntity):
    """Define a SmartThings update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    @property
    def installed_version(self) -> str | None:
        """Return the installed version of the entity."""
        return self.get_attribute_value(
            Capability.FIRMWARE_UPDATE, Attribute.CURRENT_VERSION
        )

    @property
    def latest_version(self) -> str | None:
        """Return the available version of the entity."""
        return self.get_attribute_value(
            Capability.FIRMWARE_UPDATE, Attribute.AVAILABLE_VERSION
        )

    @property
    def in_progress(self) -> bool:
        """Return if the entity is in progress."""
        return (
            self.get_attribute_value(Capability.FIRMWARE_UPDATE, Attribute.STATE)
            == "updateInProgress"
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the firmware update."""
        await self.execute_device_command(
            Capability.FIRMWARE_UPDATE,
            Command.UPDATE_FIRMWARE,
        )

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Return if the latest version is newer."""
        return AwesomeVersion(
            f"0x{latest_version}", ensure_strategy=[AwesomeVersionStrategy.HEXVER]
        ) > AwesomeVersion(
            f"0x{installed_version}", ensure_strategy=[AwesomeVersionStrategy.HEXVER]
        )
