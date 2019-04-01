"""Support for the Philips Hue sensors."""
import asyncio
from datetime import timedelta
import logging
from time import monotonic

import async_timeout

from homeassistant.components import hue
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import (
    DEVICE_CLASS_ILLUMINANCE, DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow


DEPENDENCIES = ['hue']
SCAN_INTERVAL = timedelta(seconds=5)

PRESENCE_NAME_FORMAT = "{} presence"
LIGHT_LEVEL_NAME_FORMAT = "{} light level"
TEMPERATURE_NAME_FORMAT = "{} temperature"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Hue sensors from a config entry."""
    bridge = hass.data[hue.DOMAIN][config_entry.data['host']]
    cur_sensors = {}

    async def async_update_bridge(now):
        """Update the values of the bridge.

        Will update sensors from the bridge.
        """

        await async_update_items(
            hass, bridge, async_add_entities, cur_sensors)

        async_track_point_in_utc_time(
            hass, async_update_bridge, utcnow() + SCAN_INTERVAL)

    await async_update_bridge(None)


async def async_update_items(hass, bridge, async_add_entities, current):
    """Update sensors from the bridge."""
    import aiohue

    api = bridge.api.sensors

    try:
        start = monotonic()
        with async_timeout.timeout(4):
            await api.update()
    except (asyncio.TimeoutError, aiohue.AiohueException) as err:
        _LOGGER.debug('Failed to fetch sensor: %s', err)

        if not bridge.available:
            return

        _LOGGER.error('Unable to reach bridge %s (%s)', bridge.host, err)
        bridge.available = False

        return

    finally:
        _LOGGER.debug('Finished sensor request in %.3f seconds',
                      monotonic() - start)

    if not bridge.available:
        _LOGGER.info('Reconnected to bridge %s', bridge.host)
        bridge.available = True

    new_sensors = []
    sensor_device_names = {}

    # Physical Hue motion sensors present as three sensors in the API: a
    # presence sensor, a temperature sensor, and a light level sensor. Of
    # these, only the presence sensor is assigned the user-friendly name that
    # the user has given to the device. Each of these sensors is linked by a
    # common device_id, which is the first twenty-three characters of the
    # unique id (then followed by a hyphen and an ID specific to the individual
    # sensor).
    #
    # To set up neat values, and assign the sensor entities to the same device,
    # we first, iterate over all the sensors and find the Hue presence sensors,
    # then iterate over all the remaining sensors - finding the remaining ones
    # that may or may not be related to the presence sensors.
    for item_id in api:
        if item_id in current:
            continue

        name = PRESENCE_NAME_FORMAT.format(api[item_id].name)
        if api[item_id].type == aiohue.sensors.TYPE_ZLL_PRESENCE:
            sensor = HuePresence(api[item_id], name, bridge)
            sensor_device_names[s.device_id] = api[item_id]
            current[item_id] = s
            new_sensors.append(s)

    # Iterate again now we have all the presence sensors, and add the related
    # sensors with nice names.
    for item_id in api:
        if item_id in current:
            continue

        # Work out the shared device ID, as described above
        device_id = api[item_id].uniqueid
        if device_id and len(device_id) > 23:
            device_id = device_id[:23]
        name = api[item_id].name
        primary_sensor = None
        if api[item_id].type == aiohue.sensors.TYPE_ZLL_LIGHTLEVEL:
            if device_id in sensor_device_names:
                primary_sensor = sensor_device_names[device_id]
                name = LIGHT_LEVEL_NAME_FORMAT.format(
                    primary_sensor.name)
            current[item_id] = HueLightLevel(
                api[item_id], name, bridge, primary_sensor=primary_sensor)
        elif api[item_id].type == aiohue.sensors.TYPE_ZLL_TEMPERATURE:
            if device_id in sensor_device_names:
                primary_sensor = sensor_device_names[device_id]
                name = TEMPERATURE_NAME_FORMAT.format(
                    primary_sensor.name)
            current[item_id] = HueTemperature(
                api[item_id], name, bridge, primary_sensor=primary_sensor)
        else:
            continue

        new_sensors.append(current[item_id])

    if new_sensors:
        async_add_entities(new_sensors)


class GenericHueSensor:
    """Representation of a Hue sensor."""

    should_poll = False

    def __init__(self, sensor, name, bridge, primary_sensor=None):
        """Initialize the sensor."""
        self.sensor = sensor
        self._primary_sensor = primary_sensor
        self._name = name
        self.bridge = bridge

        if self.swupdatestate == "readytoinstall":
            err = (
                "Please check for software updates of the %s "
                "sensor in the Philips Hue App."
            )
            _LOGGER.warning(err, self.name)

    @property
    def primary_sensor(self):
        """Return the entity which represents the primary sensor of
        this device.
        """

        return self._primary_sensor or self.sensor

    @property
    def device_id(self):
        """Return the ID that represents the physical device this
        sensor is part of.
        """
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
        """The state of available software updates for this device."""
        return self.primary_sensor.raw.get('swupdate', {}).get('state')

    @property
    def device_info(self):
        """Return the device info to link individual entities together
        in the hass device registry.
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
            "battery": self.sensor.battery,
            "last_updated": self.sensor.lastupdated,
            "on": self.sensor.on,
            "reachable": self.sensor.reachable,
        }


class HuePresence(GenericZLLSensor, BinarySensorDevice):
    """The presence sensor entity for a Hue motion sensor device."""

    device_class = 'presence'
    icon = 'mdi:run'

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.sensor.presence


class HueLightLevel(GenericZLLSensor, Entity):
    """The light level sensor entity for a Hue motion sensor device."""

    device_class = DEVICE_CLASS_ILLUMINANCE
    unit_of_measurement = "Lux"

    @property
    def state(self):
        """Return the state of the device."""
        return self.sensor.lightlevel

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = super().device_state_attributes
        attributes.update({
            "is_dark": self.sensor.dark,
            "is_daylight": self.sensor.daylight,
            "threshold_dark": self.sensor.tholddark,
            "threshold_offset": self.sensor.tholdoffset,
        })
        return attributes


class HueTemperature(GenericZLLSensor, Entity):
    """The temperature sensor entity for a Hue motion sensor device."""

    device_class = DEVICE_CLASS_TEMPERATURE
    unit_of_measurement = TEMP_CELSIUS

    @property
    def state(self):
        """Return the state of the device."""
        return self.sensor.temperature / 100
