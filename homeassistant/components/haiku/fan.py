"""Platform for Haiku integration."""
from haiku import fan
from haiku import discover
import asyncio
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity import Entity
from homeassistant.core import callback
from homeassistant.components.fan import (
    ATTR_SPEED,
    SPEED_OFF,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    ATTR_SPEED_LIST,
    SUPPORT_SET_SPEED,
    ENTITY_ID_FORMAT,
    FanEntity,
)
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_VALUE_TEMPLATE,
    EVENT_HOMEASSISTANT_START,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
import logging

_LOGGER = logging.getLogger(__name__)
SPEED_1 = "Speed 1"
SPEED_2 = "Speed 2"
SPEED_3 = "Speed 3"
SPEED_4 = "Speed 4"
SPEED_5 = "Speed 5"
SPEED_6 = "Speed 6"
SPEED_7 = "Speed 7"
ATTR_SPEED = "speed"
ATTR_SPEED_LIST = "speed_list"
CONF_SET_SPEED_ACTION = "async_set_speed"

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Haiku platform."""
    devices = asyncio.run(discover.discover())
    addlist = []
    if devices[1] == [] or devices is False:
        return False
    for devicesrun in range(len(devices[1])):
        afan = ""
        fanlist = (devices[1])[devicesrun]
        afan = HaikuFan(hass, fanlist[2], fanlist[3], fanlist[1])
        afan.name = fanlist[0]
        addlist.append(afan)
    add_entities(addlist)


class HaikuFan(Entity):
    """Representation of a fan."""

    _name = None  # type: str

    def __init__(self, hass, uid, cip, hstr):
        """Initialize the fan."""
        self._hass = hass
        self._cip = cip
        self._hstr = hstr
        self._state = None
        self._entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, self.name, hass=hass
        )
        self._unique_id = uid
        self._speed_list = []
        self._supported_features = 0
        self._state = STATE_ON
        self._supported_features = SUPPORT_SET_SPEED
        self._speed_list = [
            SPEED_OFF,
            SPEED_1,
            SPEED_2,
            SPEED_3,
            SPEED_4,
            SPEED_5,
            SPEED_6,
            SPEED_7,
        ]
        self._speed = SPEED_1
        self._state = SPEED_1
        self._entities = self._entity_id

    @property
    def name(self):
        """Return the display name of this fan."""
        return self._name

    @name.setter
    def name(self, name):
        """Set the name of the fan."""
        self._name = name

    @property
    def unique_id(self):
        """Return the display name of this fan."""
        return self._unique_id

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return self._speed_list

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        return {ATTR_SPEED_LIST: self.speed_list}

    @property
    def state_attributes(self) -> dict:
        """Return optional state attributes."""
        data = {}
        data[ATTR_SPEED] = self.speed
        return data

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state != STATE_OFF

    @property
    def state(self):
        """Return state of device."""
        return self._state

    @property
    def speed(self):
        """Return the current speed."""
        if self._speed in self._speed_list:
            return self._speed
        else:
            self._speed = SPEED_OFF
            self._state = STATE_OFF
        return self._speed
    async def async_update(self):
        """Update state of device."""
        updatestate = await fan.getspeed(self._cip)
        if updatestate is none or updatestate is False:
            self._state = STATE_OFF
            self._speed = SPEED_OFF
        elif updatstate == "0":
            self._state = STATE_OFF
            self._speed = SPEED_OFF
        else:
            self._speed = "Speed "+updatestate
            self._state = "Speed "+updatestate
    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if speed in self._speed_list:
            hcspeed = (speed.split(" "))[1]
            await fan.setspeed(self._cip, ("" + str(hcspeed)))
            self._speed = speed
            self._state = speed
        else:
            _LOGGER.error(
                "Received invalid speed: %s. Expected: %s.", speed, self._speed_list
            )

    async def async_turn_on(self, speed: str = None) -> None:
        """Turn on the fan."""
        if speed == "off":
            await self.async_turn_off()
        elif speed is not None:
            await self.async_set_speed(speed)
        else:
            await fan.setstate(self._cip, True)

    # pylint: disable=arguments-differ
    async def async_turn_off(self) -> None:
        """Turn off the fan."""
        await fan.setstate(self._cip, False)
