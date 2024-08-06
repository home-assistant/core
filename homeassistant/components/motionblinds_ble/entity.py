"""Base entities for the Motionblinds Bluetooth integration."""

import logging

from motionblindsble.const import MotionBlindType
from motionblindsble.device import MotionDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import CONF_BLIND_TYPE, CONF_MAC_CODE, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class MotionblindsBLEEntity(Entity):
    """Base class for Motionblinds Bluetooth entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    device: MotionDevice
    entry: ConfigEntry

    def __init__(
        self,
        device: MotionDevice,
        entry: ConfigEntry,
        entity_description: EntityDescription,
        unique_id_suffix: str | None = None,
    ) -> None:
        """Initialize the entity."""
        if unique_id_suffix is None:
            self._attr_unique_id = entry.data[CONF_ADDRESS]
        else:
            self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{unique_id_suffix}"
        self.device = device
        self.entry = entry
        self.entity_description = entity_description
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, entry.data[CONF_ADDRESS])},
            manufacturer=MANUFACTURER,
            model=MotionBlindType[entry.data[CONF_BLIND_TYPE].upper()].value,
            name=device.display_name,
        )

    async def async_update(self) -> None:
        """Update state, called by HA if there is a poll interval and by the service homeassistant.update_entity."""
        _LOGGER.debug("(%s) Updating entity", self.entry.data[CONF_MAC_CODE])
        await self.device.status_query()
