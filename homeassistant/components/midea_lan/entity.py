"""Base entity for Midea Lan."""

import logging
from typing import Any

from midealocal.device import MideaDevice

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .device_catalog import MIDEA_DEVICE_NAMES

_LOGGER = logging.getLogger(__name__)


class MideaEntity(Entity):
    """Base Midea entity."""

    _attr_has_entity_name = True

    def __init__(self, device: MideaDevice, entity_key: str) -> None:
        """Initialize Midea base entity."""
        self._device = device
        self._device.register_update(self.update_state)
        self._entity_key = entity_key
        self._unique_id = f"{DOMAIN}.{self._device.device_id}_{entity_key}"
        self.entity_id = self._unique_id
        self._device_name = self._device.name

    @property
    def device(self) -> MideaDevice:
        """Return device structure."""
        return self._device

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            manufacturer="Midea",
            model=MIDEA_DEVICE_NAMES.get(self._device.device_type, "Unknown"),
            identifiers={(DOMAIN, str(self._device.device_id))},
            name=self._device_name,
            model_id=str(self._device.device_type),
            hw_version=str(self._device.subtype),
        )

    @property
    def unique_id(self) -> str:
        """Return entity unique id."""
        return self._unique_id

    @property
    def should_poll(self) -> bool:
        """Return true is integration should poll."""
        return False

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return bool(self._device.available)

    @callback
    def update_state(self, status: Any) -> None:
        """Update entity state."""
        if not self.hass:
            _LOGGER.warning(
                "MideaEntity update_state for %s [%s] with status %s: HASS is None",
                self.name,
                type(self),
                status,
            )
            return

        if self.hass.is_stopping:
            _LOGGER.debug(
                "MideaEntity update_state for %s [%s] with status %s: HASS is stopping",
                self.name,
                type(self),
                status,
            )
            return

        if self._entity_key in status or "available" in status:
            self.schedule_update_ha_state()
