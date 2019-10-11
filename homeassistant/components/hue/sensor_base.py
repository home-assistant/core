"""Support for the Philips Hue sensors as a platform."""
import logging

from homeassistant.components import hue
from homeassistant.exceptions import NoEntitySpecifiedError

from .sensor_manager import SensorManager

CURRENT_SENSORS = "current_sensors"
SENSOR_MANAGER_FORMAT = "{}_sensor_manager"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities, binary=False):
    """Set up the Hue sensors from a config entry."""
    bridge = hass.data[hue.DOMAIN][config_entry.data["host"]]
    hass.data[hue.DOMAIN].setdefault(CURRENT_SENSORS, {})

    sm_key = SENSOR_MANAGER_FORMAT.format(config_entry.data["host"])
    manager = hass.data[hue.DOMAIN].get(sm_key)
    if manager is None:
        manager = SensorManager(hass, bridge)
        hass.data[hue.DOMAIN][sm_key] = manager

    manager.register_component(binary, async_add_entities)
    await manager.start()


class GenericHueSensor:
    """Representation of a Hue sensor."""

    should_poll = False

    def __init__(self, sensor, name, bridge, primary_sensor=None):
        """Initialize the sensor."""
        self.sensor = sensor
        self._name = name
        self._primary_sensor = primary_sensor
        self.bridge = bridge

    async def _async_update_ha_state(self, *args, **kwargs):
        raise NotImplementedError

    @property
    def primary_sensor(self):
        """Return the primary sensor entity of the physical device."""
        return self._primary_sensor or self.sensor

    @property
    def device_id(self):
        """Return the ID of the physical device this sensor is part of."""
        return self.unique_id[:23]

    @property
    def unique_id(self):
        """Return the ID of this Hue sensor."""
        return self.sensor.uniqueid

    @property
    def name(self):
        """Return a friendly name for the sensor."""
        return self._name

    @property
    def available(self):
        """Return if sensor is available."""
        return self.bridge.available and (
            self.bridge.allow_unreachable or self.sensor.config["reachable"]
        )

    @property
    def swupdatestate(self):
        """Return detail of available software updates for this device."""
        return self.primary_sensor.raw.get("swupdate", {}).get("state")

    async def async_maybe_update_ha_state(self):
        """Try to update Home Assistant with current state of entity.

        But if it's not been added to hass yet, then don't throw an error.
        """
        try:
            await self._async_update_ha_state()
        except (RuntimeError, NoEntitySpecifiedError):
            _LOGGER.debug("Hue sensor update requested before it has been added.")

    @property
    def device_info(self):
        """Return the device info.

        Links individual entities together in the hass device registry.
        """
        return {
            "identifiers": {(hue.DOMAIN, self.device_id)},
            "name": self.primary_sensor.name,
            "manufacturer": self.primary_sensor.manufacturername,
            "model": (self.primary_sensor.productname or self.primary_sensor.modelid),
            "sw_version": self.primary_sensor.swversion,
            "via_device": (hue.DOMAIN, self.bridge.api.config.bridgeid),
        }


class GenericZLLSensor(GenericHueSensor):
    """Representation of a Hue-brand, physical sensor."""

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {"battery_level": self.sensor.battery}
