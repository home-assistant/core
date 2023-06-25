"""Update entities for Linn devices."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up update entities for Reolink component."""

    _LOGGER.debug("Setting up config entry: %s", config_entry.unique_id)

    device = hass.data[DOMAIN][config_entry.entry_id]

    entity = OpenhomeUpdateEntity(device)

    await entity.async_update()

    async_add_entities([entity])


class OpenhomeUpdateEntity(UpdateEntity):
    """Update entity for a Linn DS device."""

    def __init__(self, device):
        """Initialize a Linn DS update entity."""
        self._attr_device_class = UpdateDeviceClass.FIRMWARE
        self._attr_supported_features = UpdateEntityFeature.INSTALL
        self._name = None
        self._device = device
        self._installed_version = None
        self._latest_version = None
        self._release_summary = None
        self._release_url = None

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._device.uuid()}-update"

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self._name} Firmware Update"

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return self._installed_version

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self._latest_version

    @property
    def release_summary(self) -> str | None:
        """Description of the latest firmware release."""
        return self._release_summary

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        return self._release_url

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._device.uuid()),
            },
            manufacturer=self._device.device.manufacturer,
            model=self._device.device.model_name,
            name=self._device.device.friendly_name,
        )

    async def async_update(self) -> None:
        """Update state of entity."""

        self._name = await self._device.room()

        software_status = await self._device.software_status()

        if not software_status:
            return

        self._installed_version = software_status["current_software"]["version"]

        if software_status["status"] == "update_available":
            self._latest_version = software_status["update_info"]["updates"][0][
                "version"
            ]
            self._release_summary = software_status["update_info"]["updates"][0][
                "description"
            ]
            self._release_url = software_status["update_info"]["releasenotesuri"]

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest firmware version."""
        try:
            if self.latest_version:
                await self._device.update_firmware()
        except Exception as err:
            raise HomeAssistantError(
                f"Error updating {self._device.device.friendly_name}: {err}"
            ) from err
