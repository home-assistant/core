"""An abstract class common to all IMOU entities."""

from __future__ import annotations

import logging

from pyimouapi.ha_device import DeviceStatus, ImouHaDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ImouDataUpdateCoordinator
from .const import DOMAIN, PARAM_STATE, PARAM_STATUS

_LOGGER: logging.Logger = logging.getLogger(__package__)


class ImouEntity(CoordinatorEntity):
    """Base class for all Imou entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ImouDataUpdateCoordinator,
        config_entry: ConfigEntry,
        entity_type: str,
        device: ImouHaDevice,
    ) -> None:
        """Initialize the Imou entity.

        Args:
            coordinator: Data update coordinator
            config_entry: Configuration entry
            entity_type: Type of the entity
            device: Imou device object
        """
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._entity_type = entity_type
        self._device = device

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information.

        Returns:
            DeviceInfo object containing device identifiers and metadata
        """
        return DeviceInfo(
            identifiers={
                # The combination of DeviceId and ChannelId uniquely identifies the device.
                (
                    DOMAIN,
                    f"{self._device.device_id}_{self._device.channel_id or self._device.product_id}",
                )
            },
            name=self._device.channel_name or self._device.device_name,
            manufacturer=self._device.manufacturer,
            model=self._device.model,
            sw_version=self._device.swversion,
            serial_number=self._device.device_id,
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity.

        Returns:
            Unique identifier string for the entity
        """
        return f"{self._device.device_id}_{self._device.channel_id or self._device.product_id}${self._entity_type}"

    @property
    def translation_key(self) -> str:
        """Return the translation key for this entity.

        Returns:
            Translation key string
        """
        return self._entity_type

    @property
    def available(self) -> bool:
        """Return if the entity is available.

        Returns:
            True if the entity is available, False otherwise
        """
        if self._entity_type == PARAM_STATUS:
            return True
        if PARAM_STATUS not in self._device.sensors:
            return False
        return (
            self._device.sensors[PARAM_STATUS][PARAM_STATE]
            != DeviceStatus.OFFLINE.value
        )

    @staticmethod
    def is_non_negative_number(value: str) -> bool:
        """Check if the value is a non-negative number.

        Args:
            value: String value to check

        Returns:
            True if the value is a non-negative number, False otherwise
        """
        try:
            # Try to convert the string to a float.
            number = float(value)
        except (ValueError, TypeError):
            # If conversion fails, the string is not a valid number.
            return False
        else:
            # Check if it's greater than or equal to 0.
            return number >= 0
