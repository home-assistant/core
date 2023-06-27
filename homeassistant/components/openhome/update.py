"""Update entities for Linn devices."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from async_upnp_client.client import UpnpError

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

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_has_entity_name = True
    _attr_name = "Firmware Update"

    def __init__(self, device):
        """Initialize a Linn DS update entity."""
        self._device = device
        self._attr_attr_installed_version = None
        self._attr_latest_version = None
        self._attr_release_summary = None
        self._attr_release_url = None

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._device.uuid()}-update"

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._device.uuid()),
            },
            manufacturer=self._device.manufacturer(),
            model=self._device.model_name(),
            name=self._device.friendly_name(),
        )

    async def async_update(self) -> None:
        """Update state of entity."""

        software_status = await self._device.software_status()

        self._attr_installed_version = None
        self._attr_latest_version = None
        self._attr_release_summary = None
        self._attr_release_url = None

        if software_status:
            self._attr_installed_version = software_status["current_software"][
                "version"
            ]

            if software_status["status"] == "update_available":
                self._attr_latest_version = software_status["update_info"]["updates"][
                    0
                ]["version"]
                self._attr_release_summary = software_status["update_info"]["updates"][
                    0
                ]["description"]
                self._attr_release_url = software_status["update_info"][
                    "releasenotesuri"
                ]

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest firmware version."""
        try:
            if self.latest_version:
                await self._device.update_firmware()
        except (asyncio.TimeoutError, aiohttp.ClientError, UpnpError) as err:
            raise HomeAssistantError(
                f"Error updating {self._device.device.friendly_name}: {err}"
            ) from err
