"""Vera hub implementation."""

from __future__ import annotations

import logging

import pyvera as pv

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VeraHub:
    """Manages a Vera controller hub."""

    def __init__(
        self,
        hass: HomeAssistant,
        controller: pv.VeraController,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the Vera hub."""
        self.hass = hass
        self.controller = controller
        self.config_entry = config_entry
        self._serial_number = controller.serial_number

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the Vera controller hub."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
            manufacturer="Vera Control, Ltd",
            model="Vera Controller",
            name=f"Vera ({self.config_entry.data['vera_controller_url']})",
            sw_version=None,  # Could be added if available from controller
            configuration_url=self.config_entry.data["vera_controller_url"],
        )

    def async_update_device_registry(self) -> dr.DeviceEntry:
        """Update device registry."""
        device_registry = dr.async_get(self.hass)
        return device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            **self.device_info,
        )

    @property
    def hub_id(self) -> str:
        """Return the hub ID (serial number)."""
        return self._serial_number
