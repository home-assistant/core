"""Platform to control a Zehnder ComfoAir 350 ventilation unit."""
import logging
from typing import Optional

from comfoair.asyncio import ComfoAir

from homeassistant.components.fan import (
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import DOMAIN, ComfoAirModule

_LOGGER = logging.getLogger(__name__)

SPEED_MAPPING = {1: SPEED_OFF, 2: SPEED_LOW, 3: SPEED_MEDIUM, 4: SPEED_HIGH}
SPEED_VALUES = list(SPEED_MAPPING.values())


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
) -> None:
    """Set up the ComfoAir fan platform."""
    unit = hass.data[DOMAIN]

    async_add_entities([ComfoAirFan(ca=unit)], True)


class ComfoAirFan(FanEntity):
    """Representation of the ComfoAir fan platform."""

    def __init__(self, ca: ComfoAirModule) -> None:
        """Initialize the ComfoAir fan."""
        self._ca = ca
        self._numeric_speed = 1
        self._poweron_speed = SPEED_LOW
        self._attr = ComfoAir.FAN_SPEED_MODE

    async def async_added_to_hass(self):
        """Register for sensor updates."""

        async def async_handle_update(attr, value):
            _LOGGER.debug("Dispatcher update for %s: %s", attr, value)
            assert attr == self._attr
            if value in SPEED_MAPPING:
                self._numeric_speed = value
                if self._numeric_speed > 1:
                    self._poweron_speed = self.speed
            self.async_schedule_update_ha_state()

        self._ca.add_cooked_listener(self._attr, async_handle_update)

    @property
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

    @property
    def name(self):
        """Return the name of the fan."""
        return self._ca.name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:air-conditioner"

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    @property
    def speed(self):
        """Return the current fan mode."""
        return SPEED_MAPPING[self._numeric_speed]

    @property
    def speed_list(self):
        """List of available fan modes."""
        return SPEED_VALUES

    async def async_turn_on(self, speed: Optional[str] = None, **kwargs):
        """Turn on the fan."""
        if speed is None:
            speed = self._poweron_speed
        await self.async_set_speed(speed)

    async def async_turn_off(self, **kwargs):
        """Turn off the fan (to away)."""
        await self.async_set_speed(SPEED_OFF)

    async def async_set_speed(self, speed: str):
        """Set fan speed."""
        for key, value in SPEED_MAPPING.items():
            if value == speed:
                _LOGGER.debug("Changing fan speed to %s", speed)
                await self._ca.set_speed(key)
                break
        else:
            _LOGGER.warning("Invalid fan speed: %s", speed)
