"""Support for Vilfo Router sensors."""
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_ICON,
    ATTR_LABEL,
    ATTR_ROUTER_MANUFACTURER,
    ATTR_ROUTER_MODEL,
    ATTR_ROUTER_NAME,
    ATTR_UNIT,
    DOMAIN,
    SENSOR_TYPES,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add Vilfo Router entities from a config_entry."""
    vilfo = hass.data[DOMAIN][config_entry.entry_id]

    sensors = []

    name = ATTR_ROUTER_NAME
    device_info = {
        "identifiers": {(DOMAIN, vilfo.host, vilfo.mac_address)},
        "name": name,
        "manufacturer": ATTR_ROUTER_MANUFACTURER,
        "model": ATTR_ROUTER_MODEL,
        "sw_version": vilfo.firmware,
    }

    sensors.append(VilfoRouterLoadSensor(vilfo, device_info))
    sensors.append(VilfoRouterUptimeSensor(vilfo, device_info))

    async_add_entities(sensors, True)


class VilfoRouterSensor(Entity):
    """Define a generic Vilfo Router Sensor."""

    _name = "generic"

    def __init__(self, api, device_info):
        """Initialize."""
        self.api = api
        self._device_info = device_info
        self._unique_id = f"{self.api.unique_id}_{self._name}"
        self._state = None

    @property
    def device_info(self):
        """Return the device info."""
        return self._device_info

    @property
    def icon(self):
        """Return the icon for the sensor."""
        return SENSOR_TYPES[self._name][ATTR_ICON]

    @property
    def name(self):
        """Return the name of the sensor."""
        parent_device_name = self._device_info["name"]
        sensor_name = SENSOR_TYPES[self._name][ATTR_LABEL]
        return f"{parent_device_name} {sensor_name}"

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return SENSOR_TYPES[self._name][ATTR_UNIT]

    async def async_update(self):
        """Update the router data."""
        await self.api.async_update()


class VilfoRouterLoadSensor(VilfoRouterSensor):
    """Define a sensor for the Vilfo Router load."""

    _name = "load"

    async def async_update(self):
        """Update the sensor."""
        await super(VilfoRouterLoadSensor, self).async_update()
        self._state = self.api.data.get("load")


class VilfoRouterUptimeSensor(VilfoRouterSensor):
    """Define a sensor for the Vilfo Router uptime."""

    _name = "uptime"

    async def async_update(self):
        """Update the sensor."""
        await super(VilfoRouterUptimeSensor, self).async_update()
        self._state = self.api.data.get("uptime_minutes")
