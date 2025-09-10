"""Representation of a Haus-Bus device."""

from __future__ import annotations

import logging

from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.Configuration import (
    Configuration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.controller.params.EFirmwareId import (
    EFirmwareId,
)
from pyhausbus.Templates import Templates

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)


class HausbusDevice:
    """Common base class for Haus-Bus devices."""

    def __init__(
        self, device_id: str, sw_version: str, hw_version: str, firmware_id: EFirmwareId
    ) -> None:
        """Set up Haus-Bus device."""
        self.device_id = device_id
        self.manufacturer = "Haus-Bus.de"
        self.model_id = "Controller"
        self.name = f"Controller {self.device_id}"
        self.software_version = sw_version
        self.hardware_version = hw_version
        self.firmware_id = firmware_id
        self.hass_device_entry_id = None
        self.special_type = 0

        LOGGER.debug(f"new device {self.name}")

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer=self.manufacturer,
            model=self.model_id,
            name=self.name,
            sw_version=self.software_version,
            hw_version=self.hardware_version,
        )

    def set_config(self, configuration: Configuration) -> None:
        """Sets electronic version to generate model_id and module name."""

        self.fcke = configuration.getFCKE()
        self.special_type = configuration.getStartupDelay()

        LOGGER.debug(
            f"fcke {self.fcke}, special_type {self.special_type}, isSpecialType {self.is_special_type()}, configuration = {configuration}"
        )

        if not self.is_special_type():
            self.set_model_id(
                Templates.get_instance().getModuleName(self.firmware_id, self.fcke)
            )

    def set_model_id(self, model_id: str) -> bool:

        if self.model_id != model_id:
            LOGGER.debug(f"old model_id: {self.model_id}, new model_id: {model_id}")
            self.model_id = model_id
            self.name = f"{self.model_id} {self.device_id}"
            LOGGER.debug(f"new name {self.name}")
            return True

        return False

    def set_hass_device_entry_id(self, hass_device_entry_id: str):
        """Sets the hass device entry"""
        self.hass_device_entry_id = hass_device_entry_id

    def is_special_type(self) -> bool:
        return self.special_type == 1 or self.special_type == 2

    def is_leistungs_regler(self) -> bool:
        return self.special_type == 1

    def is_rollo_modul(self) -> bool:
        return self.special_type == 2
