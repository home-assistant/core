"""Support for WiLight Cover."""
import logging

from homeassistant.components.cover import ATTR_POSITION, CoverEntity
from homeassistant.const import STATE_CLOSING, STATE_OPENING
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DATA_DEVICE_REGISTER, WiLightDevice
from .const import (
    COVER_CLOSE,
    COVER_NONE,
    COVER_OPEN,
    COVER_STOP,
    COVER_V1,
    ITEM_COVER,
    STATE_MOTOR_STOPPED,
)

_LOGGER = logging.getLogger(__name__)


def devices_from_config(hass, discovery_info):
    """Parse configuration and add WiLights cover devices."""
    device_id = discovery_info[0]
    model = discovery_info[1]
    indexes = discovery_info[2]
    item_names = discovery_info[3]
    item_types = discovery_info[4]
    item_sub_types = discovery_info[5]
    device_client = hass.data[DATA_DEVICE_REGISTER][device_id]
    devices = []
    for i in range(0, len(indexes)):
        if item_types[i] != ITEM_COVER:
            continue
        if item_sub_types[i] == COVER_NONE:
            continue
        index = indexes[i]
        item_name = item_names[i]
        item_type = f"{item_types[i]}.{item_sub_types[i]}"
        if item_sub_types[i] == COVER_V1:
            device = WiLightCover(
                item_name, index, device_id, model, item_type, device_client
            )
        else:
            continue
        devices.append(device)
    return devices


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the WiLights platform."""
    async_add_entities(devices_from_config(hass, discovery_info))


def wilight_to_hass_position(value):
    """Convert wilight position 1..255 to hass format 0..100."""
    return min(100, round((value * 100) / 255))


def hass_to_wilight_position(value):
    """Convert hass position 0..100 to wilight 1..255 scale."""
    return min(255, round((value * 255) / 100))


class WiLightCover(WiLightDevice, CoverEntity):
    """Representation of a WiLights cover."""

    def __init__(self, item_name, index, device_id, model, item_type, client):
        """Initialize the device."""
        # WiLight specific attributes for every component type
        self._device_id = device_id
        self._index = index
        self._status = {
            "motor_state": STATE_MOTOR_STOPPED,
            "position_target": 100,
            "position_current": 100,
        }
        self._client = client
        self._name = item_name
        self._model = model
        self._type = item_type
        self._unique_id = self._device_id + self._index
        """Initialize the WiLights cover."""
        self._motor_state = STATE_MOTOR_STOPPED
        self._position = 100
        self._target = 100

    @callback
    def handle_event_callback(self, event):
        """Propagate changes through ha."""
        self._status = event
        self.async_write_ha_state()

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        self._position = wilight_to_hass_position(self._status["position_current"])
        return self._position

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        self._motor_state = self._status["motor_state"]
        return self._motor_state == STATE_OPENING

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        self._motor_state = self._status["motor_state"]
        return self._motor_state == STATE_CLOSING

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        self._motor_state = self._status["motor_state"]
        self._position = wilight_to_hass_position(self._status["position_current"])
        return self._motor_state == STATE_MOTOR_STOPPED and self._position == 0

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._client.cover_command(self._index, COVER_OPEN)

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        await self._client.cover_command(self._index, COVER_CLOSE)

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            position = hass_to_wilight_position(kwargs[ATTR_POSITION])
            await self._client.set_cover_position(self._index, position)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._client.cover_command(self._index, COVER_STOP)

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
