"""Support for the Philips Hue sensors as a platform."""
import asyncio
from datetime import timedelta
import logging
from time import monotonic

import async_timeout

from homeassistant.components import hue
from homeassistant.exceptions import NoEntitySpecifiedError
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow


CURRENT_SENSORS = 'current_sensors'
SENSOR_MANAGER = 'sensor_manager'

_LOGGER = logging.getLogger(__name__)


def _device_id(aiohue_sensor):
    # Work out the shared device ID, as described below
    device_id = aiohue_sensor.uniqueid
    if device_id and len(device_id) > 23:
        device_id = device_id[:23]
    return device_id


async def async_setup_entry(hass, config_entry, async_add_entities,
                            binary=False):
    """Set up the Hue sensors from a config entry."""
    bridge = hass.data[hue.DOMAIN][config_entry.data['host']]
    hass.data[hue.DOMAIN].setdefault(CURRENT_SENSORS, {})

    manager = hass.data[hue.DOMAIN].get(SENSOR_MANAGER)
    if manager is None:
        manager = SensorManager(hass, bridge)
        hass.data[hue.DOMAIN][SENSOR_MANAGER] = manager

    manager.register_component(binary, async_add_entities)
    await manager.start()


class SensorManager:
    """Class that handles registering and updating Hue sensor entities.

    Intended to be a singleton.
    """

    SCAN_INTERVAL = timedelta(seconds=5)
    sensor_config_map = {}

    def __init__(self, hass, bridge):
        """Initialize the sensor manager."""
        import aiohue
        from .binary_sensor import HuePresence, PRESENCE_NAME_FORMAT
        from .sensor import (
            HueLightLevel, HueTemperature, LIGHT_LEVEL_NAME_FORMAT,
            TEMPERATURE_NAME_FORMAT)

        self.hass = hass
        self.bridge = bridge
        self._component_add_entities = {}
        self._started = False

        self.sensor_config_map.update({
            aiohue.sensors.TYPE_ZLL_LIGHTLEVEL: {
                "binary": False,
                "name_format": LIGHT_LEVEL_NAME_FORMAT,
                "class": HueLightLevel,
            },
            aiohue.sensors.TYPE_ZLL_TEMPERATURE: {
                "binary": False,
                "name_format": TEMPERATURE_NAME_FORMAT,
                "class": HueTemperature,
            },
            aiohue.sensors.TYPE_ZLL_PRESENCE: {
                "binary": True,
                "name_format": PRESENCE_NAME_FORMAT,
                "class": HuePresence,
            },
        })

    def register_component(self, binary, async_add_entities):
        """Register async_add_entities methods for components."""
        self._component_add_entities[binary] = async_add_entities

    async def start(self):
        """Start updating sensors from the bridge on a schedule."""
        # but only if it's not already started, and when we've got both
        # async_add_entities methods
        if self._started or len(self._component_add_entities) < 2:
            return

        self._started = True
        _LOGGER.info('Starting sensor polling loop with %s second interval',
                     self.SCAN_INTERVAL.total_seconds())

        async def async_update_bridge(now):
            """Will update sensors from the bridge."""
            await self.async_update_items()

            async_track_point_in_utc_time(
                self.hass, async_update_bridge, utcnow() + self.SCAN_INTERVAL)

        await async_update_bridge(None)

    async def async_update_items(self):
        """Update sensors from the bridge."""
        import aiohue

        api = self.bridge.api.sensors

        try:
            start = monotonic()
            with async_timeout.timeout(4):
                await api.update()
        except (asyncio.TimeoutError, aiohue.AiohueException) as err:
            _LOGGER.debug('Failed to fetch sensor: %s', err)

            if not self.bridge.available:
                return

            _LOGGER.error('Unable to reach bridge %s (%s)', self.bridge.host,
                          err)
            self.bridge.available = False

            return

        finally:
            _LOGGER.debug('Finished sensor request in %.3f seconds',
                          monotonic() - start)

        if not self.bridge.available:
            _LOGGER.info('Reconnected to bridge %s', self.bridge.host)
            self.bridge.available = True

        new_sensors = []
        new_binary_sensors = []
        primary_sensor_devices = {}
        current = self.hass.data[hue.DOMAIN][CURRENT_SENSORS]

        # Physical Hue motion sensors present as three sensors in the API: a
        # presence sensor, a temperature sensor, and a light level sensor. Of
        # these, only the presence sensor is assigned the user-friendly name
        # that the user has given to the device. Each of these sensors is
        # linked by a common device_id, which is the first twenty-three
        # characters of the unique id (then followed by a hyphen and an ID
        # specific to the individual sensor).
        #
        # To set up neat values, and assign the sensor entities to the same
        # device, we first, iterate over all the sensors and find the Hue
        # presence sensors, then iterate over all the remaining sensors -
        # finding the remaining ones that may or may not be related to the
        # presence sensors.
        for item_id in api:
            if api[item_id].type != aiohue.sensors.TYPE_ZLL_PRESENCE:
                continue

            primary_sensor_devices[_device_id(api[item_id])] = api[item_id]

        # Iterate again now we have all the presence sensors, and add the
        # related sensors with nice names where appropriate.
        for item_id in api:
            existing = current.get(api[item_id].uniqueid)
            if existing is not None:
                self.hass.async_create_task(
                    existing.async_maybe_update_ha_state())
                continue

            primary_sensor = None
            sensor_config = self.sensor_config_map.get(api[item_id].type)
            if sensor_config is None:
                continue

            base_name = api[item_id].name
            primary_sensor = primary_sensor_devices.get(
                _device_id(api[item_id]))
            if primary_sensor is not None:
                base_name = primary_sensor.name
            name = sensor_config["name_format"].format(base_name)

            current[api[item_id].uniqueid] = sensor_config["class"](
                api[item_id], name, self.bridge, primary_sensor=primary_sensor)
            if sensor_config['binary']:
                new_binary_sensors.append(current[api[item_id].uniqueid])
            else:
                new_sensors.append(current[api[item_id].uniqueid])

        async_add_sensor_entities = self._component_add_entities.get(False)
        async_add_binary_entities = self._component_add_entities.get(True)
        if new_sensors and async_add_sensor_entities:
            async_add_sensor_entities(new_sensors)
        if new_binary_sensors and async_add_binary_entities:
            async_add_binary_entities(new_binary_sensors)


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
        return self.bridge.available and (self.bridge.allow_unreachable or
                                          self.sensor.config['reachable'])

    @property
    def swupdatestate(self):
        """Return detail of available software updates for this device."""
        return self.primary_sensor.raw.get('swupdate', {}).get('state')

    async def async_maybe_update_ha_state(self):
        """Try to update Home Assistant with current state of entity.

        But if it's not been added to hass yet, then don't throw an error.
        """
        try:
            await self._async_update_ha_state()
        except (RuntimeError, NoEntitySpecifiedError):
            _LOGGER.debug(
                "Hue sensor update requested before it has been added.")

    @property
    def device_info(self):
        """Return the device info.

        Links individual entities together in the hass device registry.
        """
        return {
            'identifiers': {
                (hue.DOMAIN, self.device_id)
            },
            'name': self.primary_sensor.name,
            'manufacturer': self.primary_sensor.manufacturername,
            'model': (
                self.primary_sensor.productname or
                self.primary_sensor.modelid),
            'sw_version': self.primary_sensor.swversion,
            'via_hub': (hue.DOMAIN, self.bridge.api.config.bridgeid),
        }


class GenericZLLSensor(GenericHueSensor):
    """Representation of a Hue-brand, physical sensor."""

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {
            "battery_level": self.sensor.battery
        }
