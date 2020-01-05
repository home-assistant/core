"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
import logging
from typing import Dict

from aiofreepybox import Freepybox

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up the platform."""
    pass


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensors."""
    fbx = hass.data[DOMAIN]
    fbx_conf = await fbx.system.get_config()
    async_add_entities([FbxRXSensor(fbx, fbx_conf), FbxTXSensor(fbx, fbx_conf)], True)


class FbxSensor(Entity):
    """Representation of a freebox sensor."""

    _name = "generic"
    _unit = None
    _icon = None

    def __init__(self, fbx: Freepybox, fbx_conf: Dict):
        """Initialize the sensor."""
        self._fbx = fbx
        self._fbx_mac = fbx_conf["mac"]
        self._fbx_name = fbx_conf["model_info"]["pretty_name"]
        self._fbx_sw_v = fbx_conf["firmware_version"]
        self._state = None
        self._datas = None
        self._unique_id = f"{self._fbx_mac} {self._name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of the sensor."""
        return self._unit

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self._fbx_mac)},
            "identifiers": {(DOMAIN, self._fbx_mac)},
            "name": self._fbx_name,
            "manufacturer": "Freebox SAS",
            "sw_version": self._fbx_sw_v,
        }

    async def async_update(self):
        """Fetch status from freebox."""
        self._datas = await self._fbx.connection.get_status()


class FbxRXSensor(FbxSensor):
    """Update the Freebox RxSensor."""

    _name = "Freebox download speed"
    _unit = DATA_RATE_KILOBYTES_PER_SECOND
    _icon = "mdi:download-network"

    async def async_update(self):
        """Get the value from fetched datas."""
        await super().async_update()
        if self._datas is not None:
            self._state = round(self._datas["rate_down"] / 1000, 2)


class FbxTXSensor(FbxSensor):
    """Update the Freebox TxSensor."""

    _name = "Freebox upload speed"
    _unit = DATA_RATE_KILOBYTES_PER_SECOND
    _icon = "mdi:upload-network"

    async def async_update(self):
        """Get the value from fetched datas."""
        await super().async_update()
        if self._datas is not None:
            self._state = round(self._datas["rate_up"] / 1000, 2)
