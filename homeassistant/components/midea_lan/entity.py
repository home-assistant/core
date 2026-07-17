"""Base entity for Midea Lan."""

import logging
from typing import Any, override

from midealocal.device import MideaDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .device_catalog import MIDEA_DEVICE_NAMES

_LOGGER = logging.getLogger(__name__)

type MideaLanConfigEntry = ConfigEntry[MideaDevice]


class MideaEntity(Entity):
    """Base Midea entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: MideaDevice, entity_key: str) -> None:
        """Initialize Midea base entity."""
        self._device = device
        self._unique_id = f"{self._device.device_id}_{entity_key}"
        self._device_name = self._device.name

    @override
    async def async_added_to_hass(self) -> None:
        """Register update callback when entity is added."""
        self._device.register_update(self.update_state)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unregister update callback when entity is removed."""
        self._device.unregister_update(self.update_state)

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            manufacturer="Midea",
            # Map the device type (numeric ID) to a human-readable model name.
            model=MIDEA_DEVICE_NAMES.get(self._device.device_type, "Unknown"),
            identifiers={(DOMAIN, str(self._device.device_id))},
            name=self._device_name,
            model_id=str(self._device.device_type),
            hw_version=str(self._device.subtype),
        )

    @property
    @override
    def unique_id(self) -> str:
        """Return entity unique id."""
        return self._unique_id

    @property
    @override
    def available(self) -> bool:
        """Return entity availability."""
        return bool(self._device.available)

    def update_state(self, status: Any) -> None:
        """Update entity state."""
        if self.hass.is_stopping:
            _LOGGER.debug(
                "MideaEntity update_state for %s [%s] with status %s: HASS is stopping",
                self.name,
                type(self),
                status,
            )
            return

        self.schedule_update_ha_state()
