"""Support for Overkiz updates."""
from __future__ import annotations

from typing import Any

from pyoverkiz.enums import UIClass, UIWidget, UpdateBoxStatus
from pyoverkiz.models import Gateway

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantOverkizData
from .const import DOMAIN
from .entity import OverkizEntity

UPDATE_COMMAND = "update"

UPDATE_AVAILABLE_STATUS = {
    UpdateBoxStatus.READY_TO_UPDATE,
    UpdateBoxStatus.READY_TO_BE_UPDATED_BY_SERVER,
    UpdateBoxStatus.READY_TO_UPDATE_LOCALLY,
    UpdateBoxStatus.READY_TO_UPDATE_LOCALLY,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Overkiz update from a config entry."""
    data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]

    entities: list[OverkizUpdateEntity] = []

    for device in data.platforms[Platform.UPDATE]:
        if device.widget == UIWidget.POD or device.ui_class == UIClass.POD:
            for command in device.definition.commands:
                if command.command_name == UPDATE_COMMAND:
                    entities.append(
                        OverkizUpdateEntity(
                            device.device_url,
                            data.coordinator,
                        )
                    )

    async_add_entities(entities)


class OverkizUpdateEntity(OverkizEntity, UpdateEntity):
    """Define a Overkiz update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    def get_gateway(self) -> Gateway | None:
        """Get associated gateway."""
        gateways = self.coordinator.client.gateways

        if gateways:
            for gateway in gateways:
                if gateway.id == self.device.gateway_id:
                    return gateway

        return None

    @property
    def installed_version(self) -> str | None:
        """Return version currently installed."""
        gateway = self.get_gateway()

        if gateway:
            return gateway.connectivity.protocol_version

        return None

    @property
    def latest_version(self) -> str | None:
        """Return latest available version."""
        gateway = self.get_gateway()

        if (
            gateway
            and gateway.update_status in UPDATE_AVAILABLE_STATUS
            and self.installed_version is not None
        ):
            return "new version available"

        return None

    @property
    def in_progress(self) -> bool:
        """Update installation in progress."""
        gateway = self.get_gateway()

        if gateway:
            return gateway.update_status == UpdateBoxStatus.UPDATING

        return False

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""

        await self.executor.async_execute_command(UPDATE_COMMAND)
