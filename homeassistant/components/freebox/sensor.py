"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
import logging
from typing import Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN, SENSOR_UPDATE
from .router import FreeboxRouter, FreeboxSensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up the platform."""
    pass


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensors."""
    fbx = hass.data[DOMAIN]

    entities = []

    for sensor in fbx.sensors.values():
        entities.append(FbxSensor(fbx, sensor))

    async_add_entities(entities, True)


class FbxSensor(Entity):
    """Representation of a freebox sensor."""

    def __init__(self, fbx: FreeboxRouter, fbx_sensor: FreeboxSensor):
        """Initialize the sensor."""
        self._fbx = fbx
        self._fbx_sensor = fbx_sensor
        self._unique_id = f"{self._fbx.mac} {self._fbx_sensor.name}"
        self._unsub_dispatcher = None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._fbx_sensor.name

    @property
    def unit_of_measurement(self):
        """Return the unit of the sensor."""
        return self._fbx_sensor.unit

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._fbx_sensor.icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._fbx_sensor.state

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return self._fbx.device_info

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_added_to_hass(self):
        """Register state update callback."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, SENSOR_UPDATE, self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        self._unsub_dispatcher()
