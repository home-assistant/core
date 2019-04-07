"""Support for the Philips Hue sensors as a platform."""
import asyncio
from datetime import timedelta
import logging
from time import monotonic

import async_timeout

from homeassistant.components import hue
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow


SCAN_INTERVAL = timedelta(seconds=5)
CURRENT_SENSORS = 'current_sensors'

PRESENCE_NAME_FORMAT = "{} presence"
LIGHT_LEVEL_NAME_FORMAT = "{} light level"
TEMPERATURE_NAME_FORMAT = "{} temperature"


_HUE_SENSOR_TYPE_CONFIG_MAP = {}

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
    import aiohue
    from homeassistant.components.hue.binary_sensor import HuePresence
    from homeassistant.components.hue.sensor import (
        HueLightLevel, HueTemperature)

    _HUE_SENSOR_TYPE_CONFIG_MAP.update({
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

    bridge = hass.data[hue.DOMAIN][config_entry.data['host']]
    cur_sensors = hass.data[hue.DOMAIN][CURRENT_SENSORS] = {}

    async def async_update_bridge(now):
        """Update the values of the bridge.

        Will update sensors from the bridge.
        """

        await async_update_items(
            hass, bridge, async_add_entities, binary=binary)

        async_track_point_in_utc_time(
            hass, async_update_bridge, utcnow() + SCAN_INTERVAL)

    await async_update_bridge(None)


async def async_update_items(hass, bridge, async_add_entities, binary=False):
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
    primary_sensor_devices = {}
    current = hass.data[hue.DOMAIN][CURRENT_SENSORS]

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
        if api[item_id].type != aiohue.sensors.TYPE_ZLL_PRESENCE:
            continue

        primary_sensor_devices[_device_id(api[item_id])] = api[item_id]

    # Iterate again now we have all the presence sensors, and add the related
    # sensors with nice names where appropriate.
    for item_id in api:
        existing = current.get(api[item_id].uniqueid)
        if existing is not None:
            existing.async_schedule_update_ha_state()
            continue

        primary_sensor = None
        sensor_config = _HUE_SENSOR_TYPE_CONFIG_MAP.get(api[item_id].type)
        if sensor_config is None:
            continue

        if binary != sensor_config["binary"]:
            continue

        base_name = api[item_id].name
        primary_sensor = primary_sensor_devices.get(_device_id(api[item_id]))
        if primary_sensor is not None:
            base_name = primary_sensor.name
        name = sensor_config["name_format"].format(base_name)

        current[api[item_id].uniqueid] = sensor_config["class"](
                api[item_id], name, bridge, primary_sensor=primary_sensor)
        new_sensors.append(current[api[item_id].uniqueid])

    if new_sensors:
        async_add_entities(new_sensors)


class GenericHueSensor:
    """Representation of a Hue sensor."""

    should_poll = False

    def __init__(self, sensor, name, bridge, primary_sensor=None):
        """Initialize the sensor."""
        self.sensor = sensor
        self._name = name
        self._primary_sensor = primary_sensor
        self.bridge = bridge

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
            "battery_level": self.sensor.battery
        }
