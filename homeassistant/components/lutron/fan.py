from __future__ import annotations

from typing import Any
import logging

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import LUTRON_CONTROLLER, LUTRON_DEVICES, LutronDevice

_LOGGER = logging.getLogger(__name__)

def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Lutron fans."""
    devs = []
    for area_name, device in hass.data[LUTRON_DEVICES]["fan"]:
        dev = LutronFan(
            area_name, 
            device, 
            hass.data[LUTRON_CONTROLLER],
            device.uuid, 
            device.name, 
            None)
        devs.append(dev)

    add_entities(devs, True)


class LutronFan(LutronDevice, FanEntity):
    _attr_should_poll = False

    def __init__(
        self, area_name, lutron_device, controller,
        unique_id: str,
        name: str,
        preset_modes: list[str] | None,
    ) -> None:
        super().__init__(area_name, lutron_device, controller)
        self._attr_unique_id = unique_id
        self._attr_supported_features = FanEntityFeature.SET_SPEED
        self._attr_speed_count = 4
        self._prev_percentage: int | None = None
        self._percentage: int | None = None
        self._preset_modes = preset_modes
        self._preset_mode: str | None = None
        self._oscillating: bool | None = None
        self._direction: str | None = None
        self._attr_name = name

    @property
    def percentage(self) -> int | None:
        """Return the current speed."""
        #return self._percentage
        new_percentage = self._lutron_device.last_level()
        if new_percentage != 0:
            self._prev_percentage = new_percentage
        return new_percentage

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage is None:
            percentage = 0
        if percentage > 0:
            self._prev_percentage = percentage
        self._percentage = percentage
        self._lutron_device.level = percentage
        self._preset_mode = None
        self.schedule_update_ha_state()

    def turn_on(
            self, 
            percentage: int | None = None, 
            preset_mode: str | None = None, 
            **kwargs: Any) -> None:
        if preset_mode:
            self.set_preset_mode(preset_mode)
            return
        if percentage is not None:
            new_percentage = percentage
        elif self._prev_percentage == 0:
            # Default to medium speed
            new_percentage = 67
        else:
            new_percentage = self._prev_percentage
        self.set_percentage(new_percentage)

    def turn_off(self, **kwargs: Any) -> None:
        self.set_percentage(0)
    
    def update(self) -> None:
        """Call when forcing a refresh of the device."""
        # Reading the property (rather than last_level()) fetches value
        level = self._lutron_device.level
        _LOGGER.debug(
            "Lutron ID: %d updated to %f",
             self._lutron_device.id, level)
        if self._prev_percentage is None:
            self._prev_percentage = self._lutron_device.level
    
    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.id}
