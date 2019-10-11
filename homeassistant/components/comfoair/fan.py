"""Platform to control a Zehnder ComfoAir 350 ventilation unit."""
import logging

from homeassistant.components.fan import (
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN, SIGNAL_COMFOAIR_UPDATE_RECEIVED, ComfoAirModule

_LOGGER = logging.getLogger(__name__)

SPEED_MAPPING = {1: SPEED_OFF, 2: SPEED_LOW, 3: SPEED_MEDIUM, 4: SPEED_HIGH}


async def async_setup_platform(hass, conf, async_add_entities, discovery_info):
    """Set up the ComfoAir fan platform."""
    unit = hass.data[DOMAIN]

    async_add_entities([ComfoAirFan(hass, ca=unit)], True)


class ComfoAirFan(FanEntity):
    """Representation of the ComfoAir fan platform."""

    def __init__(self, hass, ca: ComfoAirModule) -> None:
        """Initialize the ComfoAir fan."""
        self._ca = ca
        self._speed = 1
        self._saved_speed = 2
        self._sensor_id = 0xCE

        def _update_state(cmd, data):
            if cmd == self._sensor_id and len(data) >= 9:
                speed = data[8]
                if 1 <= speed <= 4:
                    self._speed = speed

        @callback
        def async_handle_update(var):
            cmd, data = var
            if cmd == self._sensor_id:
                _LOGGER.debug("Dispatcher update for %#x: %s", cmd, data.hex())
                _update_state(cmd, data)
                self.async_schedule_update_ha_state()

        data = self._ca[self._sensor_id]
        if data:
            _update_state(self._sensor_id, data)

        # Register for dispatcher updates
        async_dispatcher_connect(
            hass, SIGNAL_COMFOAIR_UPDATE_RECEIVED, async_handle_update
        )

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
        return SPEED_MAPPING[self._speed]

    @property
    def speed_list(self):
        """List of available fan modes."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    def async_turn_on(self, speed: str = None, **kwargs):
        """Turn on the fan."""
        if speed is None:
            return self.__ca_set_speed(self._saved_speed)

        return self.async_set_speed(speed)

    def async_turn_off(self, **kwargs):
        """Turn off the fan (to away)."""
        if self._speed > 1:
            self._saved_speed = self._speed
        return self.__ca_set_speed(1)

    def async_set_speed(self, speed: str):
        """Set fan speed."""
        for key, value in SPEED_MAPPING.items():
            if value == speed:
                return self.__ca_set_speed(key)

        # shouldn't happen
        return self.async_turn_off()

    def __ca_set_speed(self, speed):
        _LOGGER.debug("Changing fan speed to %s", SPEED_MAPPING[speed])
        return self._ca.set_speed(speed)
