"""Platform to control a Zehnder ComfoAir Q350/450/600 ventilation unit."""
import logging

from pycomfoconnect import (
    CMD_FAN_MODE_AWAY,
    CMD_FAN_MODE_HIGH,
    CMD_FAN_MODE_LOW,
    CMD_FAN_MODE_MEDIUM,
    SENSOR_FAN_SPEED_MODE,
)

from homeassistant.components.fan import (
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED, ComfoConnectBridge

_LOGGER = logging.getLogger(__name__)

SPEED_MAPPING = {0: SPEED_OFF, 1: SPEED_LOW, 2: SPEED_MEDIUM, 3: SPEED_HIGH}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ComfoConnect fan platform."""
    ccb = hass.data[DOMAIN]

    add_entities([ComfoConnectFan(ccb.name, ccb)], True)


class ComfoConnectFan(FanEntity):
    """Representation of the ComfoConnect fan platform."""

    def __init__(self, name, ccb: ComfoConnectBridge) -> None:
        """Initialize the ComfoConnect fan."""
        self._ccb = ccb
        self._name = name

    async def async_added_to_hass(self):
        """Register for sensor updates."""
        _LOGGER.debug("Registering for fan speed")
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(SENSOR_FAN_SPEED_MODE),
                self._handle_update,
            )
        )
        await self.hass.async_add_executor_job(
            self._ccb.comfoconnect.register_sensor, SENSOR_FAN_SPEED_MODE
        )

    def _handle_update(self, value):
        """Handle update callbacks."""
        _LOGGER.debug(
            "Handle update for fan speed (%d): %s", SENSOR_FAN_SPEED_MODE, value
        )
        self._ccb.data[SENSOR_FAN_SPEED_MODE] = value
        self.schedule_update_ha_state()

    @property
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._ccb.unique_id

    @property
    def name(self):
        """Return the name of the fan."""
        return self._name

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
        try:
            speed = self._ccb.data[SENSOR_FAN_SPEED_MODE]
            return SPEED_MAPPING[speed]
        except KeyError:
            return None

    @property
    def speed_list(self):
        """List of available fan modes."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the fan."""
        if speed is None:
            speed = SPEED_LOW
        self.set_speed(speed)

    def turn_off(self, **kwargs) -> None:
        """Turn off the fan (to away)."""
        self.set_speed(SPEED_OFF)

    def set_speed(self, speed: str):
        """Set fan speed."""
        _LOGGER.debug("Changing fan speed to %s", speed)

        if speed == SPEED_OFF:
            self._ccb.comfoconnect.cmd_rmi_request(CMD_FAN_MODE_AWAY)
        elif speed == SPEED_LOW:
            self._ccb.comfoconnect.cmd_rmi_request(CMD_FAN_MODE_LOW)
        elif speed == SPEED_MEDIUM:
            self._ccb.comfoconnect.cmd_rmi_request(CMD_FAN_MODE_MEDIUM)
        elif speed == SPEED_HIGH:
            self._ccb.comfoconnect.cmd_rmi_request(CMD_FAN_MODE_HIGH)

        # Update current mode
        self.schedule_update_ha_state()
