"""Entities for Synology DSM."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .common import SynoApi
from .const import ATTRIBUTION, DOMAIN


@dataclass
class SynologyDSMRequiredKeysMixin:
    """Mixin for required keys."""

    api_key: str


@dataclass
class SynologyDSMEntityDescription(EntityDescription, SynologyDSMRequiredKeysMixin):
    """Generic Synology DSM entity description."""


class SynologyDSMBaseEntity(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, dict[str, Any]]]]
):
    """Representation of a Synology NAS entry."""

    entity_description: SynologyDSMEntityDescription
    unique_id: str
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        api: SynoApi,
        coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]],
        description: SynologyDSMEntityDescription,
    ) -> None:
        """Initialize the Synology DSM entity."""
        super().__init__(coordinator)
        self.entity_description = description

        self._api = api
        self._attr_name = f"{api.network.hostname} {description.name}"
        self._attr_unique_id: str = (
            f"{api.information.serial}_{description.api_key}:{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._api.information.serial)},
            name=self._api.network.hostname,
            manufacturer="Synology",
            model=self._api.information.model,
            sw_version=self._api.information.version_string,
            configuration_url=self._api.config_url,
        )

    async def async_added_to_hass(self) -> None:
        """Register entity for updates from API."""
        self.async_on_remove(
            self._api.subscribe(self.entity_description.api_key, self.unique_id)
        )
        await super().async_added_to_hass()


class SynologyDSMDeviceEntity(SynologyDSMBaseEntity):
    """Representation of a Synology NAS disk or volume entry."""

    def __init__(
        self,
        api: SynoApi,
        coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]],
        description: SynologyDSMEntityDescription,
        device_id: str | None = None,
    ) -> None:
        """Initialize the Synology DSM disk or volume entity."""
        super().__init__(api, coordinator, description)
        self._device_id = device_id
        self._device_name: str | None = None
        self._device_manufacturer: str | None = None
        self._device_model: str | None = None
        self._device_firmware: str | None = None
        self._device_type = None

        if "volume" in description.key:
            volume = self._api.storage.get_volume(self._device_id)
            # Volume does not have a name
            self._device_name = volume["id"].replace("_", " ").capitalize()
            self._device_manufacturer = "Synology"
            self._device_model = self._api.information.model
            self._device_firmware = self._api.information.version_string
            self._device_type = (
                volume["device_type"]
                .replace("_", " ")
                .replace("raid", "RAID")
                .replace("shr", "SHR")
            )
        elif "disk" in description.key:
            disk = self._api.storage.get_disk(self._device_id)
            self._device_name = disk["name"]
            self._device_manufacturer = disk["vendor"]
            self._device_model = disk["model"].strip()
            self._device_firmware = disk["firm"]
            self._device_type = disk["diskType"]

        self._attr_name = (
            f"{self._api.network.hostname} ({self._device_name}) {description.name}"
        )
        self._attr_unique_id += f"_{self._device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self._api.information.serial}_{self._device_id}")},
            name=f"{self._api.network.hostname} ({self._device_name})",
            manufacturer=self._device_manufacturer,
            model=self._device_model,
            sw_version=self._device_firmware,
            via_device=(DOMAIN, self._api.information.serial),
            configuration_url=self._api.config_url,
        )
