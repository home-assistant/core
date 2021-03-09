"""Support for Freebox covers."""
import logging
import json
import time
from homeassistant.core import callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.cover import CoverEntity, DEVICE_CLASS_SHUTTER, DEVICE_CLASS_AWNING, DEVICE_CLASS_GARAGE
from .const import DOMAIN
from .base_class import FreeboxHomeBaseClass

from homeassistant.const import (
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities) -> None:
    router = hass.data[DOMAIN][entry.unique_id]
    tracked = set()

    @callback
    def update_callback():
        add_entities(hass, router, async_add_entities, tracked)

    router.listeners.append(async_dispatcher_connect(hass, router.signal_home_device_new, update_callback))
    update_callback()


@callback
def add_entities(hass, router, async_add_entities, tracked):
    """Add new Alarm Control Panel from the router."""
    new_tracked = []

    for nodeId, node in router.home_devices.items():
        if (nodeId in tracked):
            continue
        if (node["category"]=="basic_shutter"):
            new_tracked.append(FreeboxBasicShutter(hass, router, node))
            tracked.add(nodeId)
        elif (node["category"]=="opener"):
            new_tracked.append(FreeboxOpener(hass, router, node))
            tracked.add(nodeId)

    if new_tracked:
        async_add_entities(new_tracked, True)



class FreeboxBasicShutter(FreeboxHomeBaseClass,CoverEntity):

    def __init__(self, hass, router, node) -> None:
        """Initialize a Cover"""
        super().__init__(hass, router, node)
        self._command_up    = self.get_command_id(node['show_endpoints'], "slot", "up")
        self._command_stop  = self.get_command_id(node['show_endpoints'], "slot", "stop")
        self._command_down  = self.get_command_id(node['show_endpoints'], "slot", "down")
        self._command_state = self.get_command_id(node['show_endpoints'], "signal", "state")
        self._state = self.convert_state(self.get_value("signal", "state"))

    @property
    def device_class(self) -> str:
        return DEVICE_CLASS_SHUTTER

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        if(self._state == STATE_OPEN):
            return False
        if(self._state == STATE_CLOSED):
            return True
        return None

    async def async_open_cover(self, **kwargs):
        """Open cover."""
        await self.set_home_endpoint_value(self._command_up, {"value": None})
        await self.async_set_value("signal", "state", False)

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        await self.set_home_endpoint_value(self._command_down, {"value": None})
        await self.async_set_value("signal", "state", True)

    async def async_stop_cover(self, **kwargs):
        """Stop cover."""
        await self.set_home_endpoint_value(self._command_stop, {"value": None})
        await self.async_set_value("signal", "state", None)

    async def async_update_node(self):
        """Update state"""
        self._state = self.convert_state(self.get_value("signal", "state"))

    def convert_state(self, state):
        if( state ): 
            return STATE_CLOSED
        elif( state is not None):
            return STATE_OPEN
        else:
            return None



class FreeboxOpener(FreeboxHomeBaseClass,CoverEntity):

    def __init__(self, hass, router, node) -> None:
        """Initialize a Cover"""
        super().__init__(hass, router, node)
        self._command_set_position  = self.get_command_id(node['show_endpoints'], "slot", "position_set")
        self._command_stop          = self.get_command_id(node['show_endpoints'], "slot", "stop")
        self._device_class          = DEVICE_CLASS_AWNING
        #self._command_state         = self.get_command_id(node['show_endpoints'], "signal", "state")
        #self._current_position      = self.get_value("signal", "state")
        self._current_position      = None

        if("Porte_Garage" in node["type"]["icon"]):
            self._device_class = DEVICE_CLASS_GARAGE

    @property
    def device_class(self) -> str:
        return self._device_class

    @property
    def current_cover_position(self):
        """Return current position of cover.
        None is unknown, 0 is closed, 100 is fully open.
        """
        if( self._current_position == None ):
            return 50
        return self._current_position

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return self._current_position == 0

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        await self.set_home_endpoint_value(self._command_set_position, {"value": 100 - kwargs[ATTR_POSITION]})
        self._current_position = 100 - kwargs[ATTR_POSITION]
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open cover."""
        await self.set_home_endpoint_value(self._command_set_position, {"value": 0})
        self._current_position = 100
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        await self.set_home_endpoint_value(self._command_set_position, {"value": 100})
        self._current_position = 0
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop cover."""
        await self.set_home_endpoint_value(self._command_stop, {"value": None})
        self._current_position = None
        self.async_write_ha_state()

    async def async_update_node(self):
        slot    = self.get_value("slot", "position_set")
        signal  = self.get_value("signal", "position_set")
        _LOGGER.warning("Position Garage [" + str(slot) + "/" + str(signal) + "]")
