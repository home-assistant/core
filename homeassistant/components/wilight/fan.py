"""Support for WiLight Fan."""
import logging

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SUPPORT_DIRECTION,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DATA_DEVICE_REGISTER, WiLightDevice
from .const import DIRECTION_OFF, FAN_NONE, FAN_V1, ITEM_FAN

SUPPORTED_SPEEDS = [SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

SUPPORTED_FEATURES = SUPPORT_SET_SPEED + SUPPORT_DIRECTION

_LOGGER = logging.getLogger(__name__)


def devices_from_config(hass, discovery_info):
    """Parse configuration and add WiLights switch devices."""
    device_id = discovery_info[0]
    model = discovery_info[1]
    indexes = discovery_info[2]
    item_names = discovery_info[3]
    item_types = discovery_info[4]
    item_sub_types = discovery_info[5]
    device_client = hass.data[DATA_DEVICE_REGISTER][device_id]
    devices = []
    for i in range(0, len(indexes)):
        if item_types[i] != ITEM_FAN:
            continue
        if item_sub_types[i] == FAN_NONE:
            continue
        index = indexes[i]
        item_name = item_names[i]
        item_type = f"{item_types[i]}.{item_sub_types[i]}"
        if item_sub_types[i] == FAN_V1:
            device = WiLightFan(
                item_name, index, device_id, model, item_type, device_client
            )
        else:
            continue
        devices.append(device)
    return devices


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the WiLights platform."""
    async_add_entities(devices_from_config(hass, discovery_info))


class WiLightFan(WiLightDevice, FanEntity):
    """Representation of a WiLights fan."""

    def __init__(self, item_name, index, device_id, model, item_type, client):
        """Initialize the device."""
        # WiLight specific attributes for every component type
        self._device_id = device_id
        self._index = index
        self._status = {}
        self._client = client
        self._name = item_name
        self._model = model
        self._type = item_type
        self._unique_id = self._device_id + self._index
        """Initialize the WiLights fan."""
        self._on = False
        self._speed = SPEED_HIGH
        self._direction = DIRECTION_FORWARD

    @callback
    def handle_event_callback(self, event):
        """Propagate changes through ha."""
        self._status = event
        self.async_write_ha_state()

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES

    @property
    def icon(self):
        """Return the icon of device based on its type."""
        return "mdi:fan"

    @property
    def is_on(self):
        """Return true if device is on."""
        self._on = self._status["direction"] != DIRECTION_OFF
        return self._on

    @property
    def speed(self) -> str:
        """Return the current speed."""
        self._speed = self._status["speed"]
        return self._status["speed"]

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return SUPPORTED_SPEEDS

    @property
    def current_direction(self) -> str:
        """Return the current direction of the fan."""
        if self._status["direction"] != DIRECTION_OFF:
            self._direction = self._status["direction"]
        return self._direction

    async def async_turn_on(self, speed: str = None, **kwargs):
        """Turn on the fan."""
        if speed is None:
            await self._client.set_fan_direction(self._index, self._direction)
        else:
            await self.async_set_speed(speed)

    async def async_set_speed(self, speed: str):
        """Set the speed of the fan."""
        self._speed = speed
        await self._client.set_fan_speed(self._index, speed)

    async def async_set_direction(self, direction: str):
        """Set the direction of the fan."""
        self._on = True
        self._direction = direction
        await self._client.set_fan_direction(self._index, direction)

    async def async_turn_off(self, **kwargs):
        """Turn the fan off."""
        self._on = False
        await self._client.set_fan_direction(self._index, DIRECTION_OFF)

    @callback
    def _availability_callback(self, availability):
        """Update availability state."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register update callback."""
        self._client.register_status_callback(self.handle_event_callback, self._index)
        self._status = await self._client.status(self._index)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"wilight_device_available_{self._device_id}",
                self._availability_callback,
            )
        )
