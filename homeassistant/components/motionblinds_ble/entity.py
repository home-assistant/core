"""Base entity for the Motionblinds BLE integration."""

import logging

from motionblindsble.device import MotionDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_BLIND_TYPE, CONF_MAC_CODE, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class MotionblindsBLEEntity(Entity):
    """Base class for Motionblinds BLE entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    _device: MotionDevice
    config_entry: ConfigEntry

    def __init__(
        self,
        device: MotionDevice,
        entry: ConfigEntry,
        unique_id_suffix: str | None = None,
    ) -> None:
        """Initialize the entity."""
        self._attr_unique_id: str = (
            entry.data[CONF_ADDRESS]
            if unique_id_suffix is None
            else f"{entry.data[CONF_ADDRESS]}_{unique_id_suffix}"
        )
        self._device = device
        self.config_entry = entry
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, entry.data[CONF_ADDRESS])},
            manufacturer=MANUFACTURER,
            model=entry.data[CONF_BLIND_TYPE],
            name=device.display_name,
        )

    async def async_update(self) -> None:
        """Update state, called by HA if there is a poll interval and by the service homeassistant.update_entity."""
        _LOGGER.debug("(%s) Updating entity", self.config_entry.data[CONF_MAC_CODE])
        await self._device.connect()
