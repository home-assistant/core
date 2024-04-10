"""Select entities for the Motionblinds Bluetooth integration."""

from __future__ import annotations

import logging

from motionblindsble.const import MotionBlindType, MotionSpeedLevel
from motionblindsble.device import MotionDevice

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_SPEED, CONF_MAC_CODE, DOMAIN
from .entity import MotionblindsBLEEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


SELECT_TYPES: dict[str, SelectEntityDescription] = {
    ATTR_SPEED: SelectEntityDescription(
        key=ATTR_SPEED,
        translation_key=ATTR_SPEED,
        entity_category=EntityCategory.CONFIG,
        options=["1", "2", "3"],
    )
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up select entities based on a config entry."""

    device: MotionDevice = hass.data[DOMAIN][entry.entry_id]

    if device.blind_type not in {MotionBlindType.CURTAIN, MotionBlindType.VERTICAL}:
        async_add_entities([SpeedSelect(device, entry, SELECT_TYPES[ATTR_SPEED])])


class SpeedSelect(MotionblindsBLEEntity, SelectEntity):
    """Representation of a speed select entity."""

    def __init__(
        self,
        device: MotionDevice,
        entry: ConfigEntry,
        entity_description: SelectEntityDescription,
    ) -> None:
        """Initialize the speed select entity."""
        super().__init__(
            device, entry, entity_description, unique_id_suffix=entity_description.key
        )
        self._attr_current_option = None

    async def async_added_to_hass(self) -> None:
        """Register device callbacks."""
        _LOGGER.debug(
            "(%s) Setting up speed select entity",
            self.entry.data[CONF_MAC_CODE],
        )
        self.device.register_speed_callback(self.async_update_speed)

    @callback
    def async_update_speed(self, speed_level: MotionSpeedLevel | None) -> None:
        """Update the speed sensor value."""
        self._attr_current_option = str(speed_level.value) if speed_level else None
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected speed sensor value."""
        speed_level = MotionSpeedLevel(int(option))
        await self.device.speed(speed_level)
        self._attr_current_option = str(speed_level.value) if speed_level else None
        self.async_write_ha_state()
