"""Support for detectors covers."""
import logging

from typing import Dict, Optional
from datetime import datetime, timedelta
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from .const import DOMAIN, VALUE_NOT_SET
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)

#from threading import Thread, Lock
#mutex = Lock()


class FreeboxHomeBaseClass(Entity):
    def __init__(self, hass, router: FreeboxRouter, node: Dict[str, any], sub_node = None) -> None:
        _LOGGER.debug(node)
        self._hass = hass
        self._router = router
        self._node  = node
        self._id    = node["id"]
        self._name  = node["label"].strip()
        self._device_name = node["label"].strip()
        self._unique_id = f"{self._router.mac}-node_{self._id}"
        self._is_device = True
        self._watcher = None

        if(sub_node != None):
            self._name = sub_node["label"].strip()
            self._unique_id += "-" + sub_node["name"].strip()

        self._available = True
        self._firmware  = node['props'].get('FwVersion', None)
        self._manufacturer = "Freebox SAS"
        self._model     = ""
        if( node["category"]=="pir" ):
            self._model     = "F-HAPIR01A"
        elif( node["category"]=="camera" ):
            self._model     = "F-HACAM01A"
        elif( node["category"]=="dws" ):
            self._model     = "F-HADWS01A"
        elif( node["category"]=="kfb" ):
            self._model     = "F-HAKFB01A"
            self._is_device = True
        elif( node["category"]=="alarm" ):
            self._model     = "F-MSEC07A"
        elif( node["type"].get("inherit", None)=="node::rts"):
            self._manufacturer  = "Somfy"
            self._model         = "RTS"

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def device_info(self):
        """Return the device info."""
        if (self._is_device == False):
            return None
        return {
            "identifiers": {(DOMAIN, self._id)},
            "name": self._device_name,
            "manufacturer": self._manufacturer,
            "model": self._model,
            "sw_version": self._firmware,
        }

    def start_watcher(self, timedelta=timedelta(seconds=1)):
        self._watcher = async_track_time_interval(self._hass, self.async_watcher, timedelta)

    def stop_watcher(self):
        if( self._watcher != None ):
            self._watcher()
            self._watcher = None

    async def async_watcher(self, now: Optional[datetime] = None) -> None:
        raise NotImplementedError()

    async def set_home_endpoint_value(self, command_id, value):
        if( command_id == VALUE_NOT_SET ):
            _LOGGER.error("Unable to SET a value through the API. Command is VALUE_NOT_SET")
            return False
        #mutex.acquire()
        #try:
        await self._router._api.home.set_home_endpoint_value(self._id, command_id, value)
        #finally:
        #    mutex.release()
        return True

    async def get_home_endpoint_value(self, command_id):
        if( command_id == VALUE_NOT_SET ):
            _LOGGER.error("Unable to GET a value through the API. Command is VALUE_NOT_SET")
            return VALUE_NOT_SET
        #mutex.acquire()
        try:
            node = await self._router._api.home.get_home_endpoint_value(self._id, command_id)        
        except TimeoutError as error:
            _LOGGER.warning("The Freebox API Timeout during a value retrieval")
            return VALUE_NOT_SET
        #finally:
        #    mutex.release()
        return node.get("value", VALUE_NOT_SET)
        
    def get_command_id(self, nodes, ep_type, name ):
        node = next(filter(lambda x: (x["name"]==name and x["ep_type"]==ep_type), nodes), None)
        if( node == None):
            _LOGGER.warning("The Freebox Home device has no value for: " + ep_type + "/" + name)
            return VALUE_NOT_SET
        return node["id"]

    def get_node_value(self, nodes, ep_type, name ):
        node = next(filter(lambda x: (x["name"]==name and x["ep_type"]==ep_type), nodes), None)
        if( node == None):
            _LOGGER.warning("The Freebox Home device has no node for: " + ep_type + "/" + name)
            return VALUE_NOT_SET
        return node.get("value", VALUE_NOT_SET)

    def set_node_value(self, nodes, ep_type, name, value ):
        node = next(filter(lambda x: (x["name"]==name and x["ep_type"]==ep_type), nodes), None)
        if( node == None):
            _LOGGER.warning("The Freebox Home device has no node for: " + ep_type + "/" + name)
            return
        node["value"] = value


    async def async_added_to_hass(self):
        #_LOGGER.warning("Home node added to hass: " + str(self.entity_id))
        self._router.home_device_uids.append(self.entity_id)

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        self.stop_watcher()
        await super().async_will_remove_from_hass()
        #_LOGGER.warning("Home node removed from to hass: " + str(self.entity_id))
