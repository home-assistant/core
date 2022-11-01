"""Support for Overkiz updates."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from pyoverkiz.enums import UIClass, UIWidget, UpdateBoxStatus
from pyoverkiz.models import Gateway

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantOverkizData
from .const import DOMAIN, LOGGER
from .coordinator import OverkizDataUpdateCoordinator
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

    gateways = await data.coordinator.client.get_gateways()
    gateway_by_ids: dict[str, Gateway] = {}
    for gateway in gateways:
        gateway_by_ids[gateway.id] = gateway

    for device in data.coordinator.data.values():
        if device.widget == UIWidget.POD or device.ui_class == UIClass.POD:
            url = urlparse(device.device_url)
            gateway_id = url.netloc
            if gateway_id in gateway_by_ids:
                LOGGER.info("POD detected for %s", gateway_id)
                for command in device.definition.commands:
                    LOGGER.info(command.command_name)
                    if command.command_name == UPDATE_COMMAND:
                        LOGGER.info(device)
                        LOGGER.info(gateway_by_ids[gateway_id])
                        async_add_entities(
                            [
                                OverkizUpdateEntity(
                                    gateway_id,
                                    device.device_url,
                                    data.coordinator,
                                )
                            ]
                        )


class OverkizUpdateEntity(OverkizEntity, UpdateEntity):
    """Define a Overkiz update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    def __init__(
        self,
        gateway_id: str,
        device_url: str,
        coordinator: OverkizDataUpdateCoordinator,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(device_url, coordinator)
        self.gateway_id = gateway_id

    def get_gateway(self) -> Gateway | None:
        """Get associated gateway."""
        gateways = self.coordinator.client.gateways

        if gateways:
            for gateway in gateways:
                if gateway.id == self.gateway_id:
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
            return self.installed_version + ".new"

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
