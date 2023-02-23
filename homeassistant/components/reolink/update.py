"""Update entities for Reolink devices."""
from __future__ import annotations

import logging
from typing import Any

from reolink_aio.exceptions import ReolinkError

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkBaseCoordinatorEntity

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up update entities for Reolink component."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]
    if reolink_data.host.api.supported(None, "update"):
        async_add_entities([ReolinkUpdateEntity(reolink_data)])


class ReolinkUpdateEntity(ReolinkBaseCoordinatorEntity, UpdateEntity):
    """Update entity for a Netgear device."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_release_url = "https://reolink.com/download-center/"
    _attr_name = "Update"

    def __init__(
        self,
        reolink_data: ReolinkData,
    ) -> None:
        """Initialize a Netgear device."""
        super().__init__(reolink_data, reolink_data.firmware_coordinator)

        self._attr_unique_id = f"{self._host.unique_id}_update"

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return self._host.api.sw_version

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if self.coordinator.data is None:
            return None

        if not self.coordinator.data:
            return self.installed_version

        return self.coordinator.data

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest firmware version."""
        try:
            await self._host.api.update_firmware()
        except ReolinkError as err:
            raise HomeAssistantError(
                f"Error trying to update Reolink firmware: {err}"
            ) from err
