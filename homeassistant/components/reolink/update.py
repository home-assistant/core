"""Update entities for Reolink devices."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Literal

from reolink_aio.exceptions import ReolinkError
from reolink_aio.software_version import NewSoftwareVersion

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkBaseCoordinatorEntity

LOGGER = logging.getLogger(__name__)

POLL_AFTER_INSTALL = 120


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up update entities for Reolink component."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([ReolinkUpdateEntity(reolink_data)])


class ReolinkUpdateEntity(
    ReolinkBaseCoordinatorEntity[str | Literal[False] | NewSoftwareVersion],
    UpdateEntity,
):
    """Update entity for a Netgear device."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_release_url = "https://reolink.com/download-center/"

    def __init__(
        self,
        reolink_data: ReolinkData,
    ) -> None:
        """Initialize a Netgear device."""
        super().__init__(reolink_data, reolink_data.firmware_coordinator)

        self._attr_unique_id = f"{self._host.unique_id}"
        self._cancel_update: CALLBACK_TYPE | None = None

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return self._host.api.sw_version

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if not self.coordinator.data:
            return self.installed_version

        if isinstance(self.coordinator.data, str):
            return self.coordinator.data

        return self.coordinator.data.version_string

    @property
    def supported_features(self) -> UpdateEntityFeature:
        """Flag supported features."""
        supported_features = UpdateEntityFeature.INSTALL
        if isinstance(self.coordinator.data, NewSoftwareVersion):
            supported_features |= UpdateEntityFeature.RELEASE_NOTES
        return supported_features

    async def async_release_notes(self) -> str | None:
        """Return the release notes."""
        if not isinstance(self.coordinator.data, NewSoftwareVersion):
            return None

        return (
            "If the install button fails, download this"
            f" [firmware zip file]({self.coordinator.data.download_url})."
            " Then, follow the installation guide (PDF in the zip file).\n\n"
            f"## Release notes\n\n{self.coordinator.data.release_notes}"
        )

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
        finally:
            self.async_write_ha_state()
            self._cancel_update = async_call_later(
                self.hass, POLL_AFTER_INSTALL, self._async_update_future
            )

    async def _async_update_future(self, now: datetime | None = None) -> None:
        """Request update."""
        await self.async_update()

    async def async_will_remove_from_hass(self) -> None:
        """Entity removed."""
        await super().async_will_remove_from_hass()
        if self._cancel_update is not None:
            self._cancel_update()
