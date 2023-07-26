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

FULL_SUPPORT = (
    FanEntityFeature.SET_SPEED
)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Lutron fans."""
    devs = []
    for area_name, device in hass.data[LUTRON_DEVICES]["fan"]:
        dev = LutronFan(area_name, device, hass.data[LUTRON_CONTROLLER],
                        hass, device.uuid, device.name, FULL_SUPPORT, None)
        devs.append(dev)

    async_add_entities(devs, True)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    await async_setup_platform(hass, {}, async_add_entities)


class LutronFan(LutronDevice, FanEntity):
    _attr_should_poll = False

    def __init__(
        self, area_name, lutron_device, controller,
        hass: HomeAssistant,
        unique_id: str,
        name: str,
        supported_features: FanEntityFeature,
        preset_modes: list[str] | None,
    ) -> None:
        self.hass = hass
        self._unique_id = unique_id
        self._attr_supported_features = supported_features
        self._prev_percentage: int | None = None
        self._percentage: int | None = None
        self._preset_modes = preset_modes
        self._preset_mode: str | None = None
        self._oscillating: bool | None = None
        self._direction: str | None = None
        self._attr_name = name
        _LOGGER.info("FANDATA: A %s B %s", (unique_id,name))
        super().__init__(area_name, lutron_device, controller)

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def percentage(self) -> int | None:
        """Return the current speed."""
        #return self._percentage
        new_percentage = self._lutron_device.last_level()
        if new_percentage != 0:
            self._prev_percentage = new_percentage
        return new_percentage

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return 4

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
        _LOGGER.debug("Lutron ID: %d updated to %f", self._lutron_device.id, level)
        if self._prev_percentage is None:
            self._prev_percentage = self._lutron_device.level
    
    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.id}
