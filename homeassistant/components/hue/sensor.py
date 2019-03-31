"""Support for the Philips Hue sensors."""
import asyncio
from datetime import timedelta
import logging
from time import monotonic

import async_timeout

from homeassistant.components import hue
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, ENTITY_ID_FORMAT as BINARY_ENTITY_ID_FORMAT)
from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT as SENSOR_ENTITY_ID_FORMAT)
from homeassistant.const import (
    DEVICE_CLASS_ILLUMINANCE, DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity, async_generate_entity_id

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

    allow_sensors = bridge.allow_sensors
    if not allow_sensors:
        _LOGGER.info(
            'Skipping Hue sensor setup. Set allow_hue_sensors to true if you '
            'don\'t want this.')
        return

    # Hue updates all sensors via a single API call.
    #
    # If we call a service to update 2 sensors, we only want the API to be
    # called once.
    #
    # The throttle decorator will return right away if a call is currently
    # in progress. This means that if we are updating 2 sensors, the first one
    # is in the update method, the second one will skip it and assume the
    # update went through and updates it's data, not good!
    #
    # The current mechanism will make sure that all sensors will wait till
    # the update call is done before writing their data to the state machine.
    #
    # An alternative approach would be to disable automatic polling by Home
    # Assistant and take control ourselves. This works great for polling as now
    # we trigger from 1 time update an update to all entities. However it gets
    # tricky from inside async_turn_on and async_turn_off.
    #
    # If automatic polling is enabled, Home Assistant will call the entity
    # update method after it is done calling all the services. This means that
    # when we update, we know all commands have been processed. If we trigger
    # the update from inside async_turn_on, the update will not capture the
    # changes to the second entity until the next polling update because the
    # throttle decorator will prevent the call.

    progress = None
    sensor_progress = set()

    async def request_update(object_id):
        """Request an update.

        We will only make 1 request to the server for updating at a time. If a
        request is in progress, we will join the request that is in progress.

        This approach is possible because should_poll=True. That means that
        Home Assistant will ask sensors for updates during a polling cycle or
        after it has called a service.

        We keep track of the sensors that are waiting for the request to
        finish. When new data comes in, we'll trigger an update for all
        non-waiting sensors. This covers the case where a service is called to
        enable 2 sensors but in the meanwhile some other sensor has changed
        too.
        """
        nonlocal progress

        sensor_progress.add(object_id)

        if progress is not None:
            return await progress

        progress = asyncio.ensure_future(update_bridge())
        result = await progress
        progress = None
        sensor_progress.clear()
        return result

    async def update_bridge():
        """Update the values of the bridge.

        Will update sensors from the bridge.
        """
        tasks = []
        tasks.append(async_update_items(
            hass, bridge, async_add_entities, request_update, cur_sensors,
            sensor_progress
        ))

        await asyncio.wait(tasks)

    await update_bridge()


async def async_update_items(hass, bridge, async_add_entities,
                             request_bridge_update, current, progress_waiting):
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

        for sensor_id, sensor in current.items():
            if sensor_id not in progress_waiting:
                sensor.async_schedule_update_ha_state()

        return

    finally:
        _LOGGER.debug('Finished sensor request in %.3f seconds',
                      monotonic() - start)

    if not bridge.available:
        _LOGGER.info('Reconnected to bridge %s', bridge.host)
        bridge.available = True

    new_sensors = []
    sensor_device_names = {}

    for item_id in api:
        if item_id not in current:
            name = PRESENCE_NAME_FORMAT.format(api[item_id].name)
            if api[item_id].type == aiohue.sensors.TYPE_ZLL_PRESENCE:
                s = HuePresence(
                    hass, api[item_id], name, request_bridge_update,
                    bridge)
                sensor_device_names[s.device_id] = api[item_id].name
                current[item_id] = s

    # Iterate again now we have all the presence sensors, and add the related
    # sensors with nice names
    for item_id in api:
        if item_id not in current:
            device_id = api[item_id].uniqueid
            if device_id and len(device_id) > 23:
                device_id = device_id[:23]
            name = api[item_id].name
            if api[item_id].type == aiohue.sensors.TYPE_ZLL_LIGHTLEVEL:
                if device_id in sensor_device_names:
                    name = LIGHT_LEVEL_NAME_FORMAT.format(
                        sensor_device_names[device_id])
                current[item_id] = HueLightLevel(
                    hass, api[item_id], name, request_bridge_update, bridge)
            elif api[item_id].type == aiohue.sensors.TYPE_ZLL_TEMPERATURE:
                if device_id in sensor_device_names:
                    name = TEMPERATURE_NAME_FORMAT.format(
                        sensor_device_names[device_id])
                current[item_id] = HueTemperature(
                    hass, api[item_id], name, request_bridge_update, bridge)

            if item_id in current:
                new_sensors.append(current[item_id])

        elif item_id not in progress_waiting:
            current[item_id].async_schedule_update_ha_state()

    if new_sensors:
        async_add_entities(new_sensors)


class GenericHueSensor:
    """Representation of a Hue sensor."""

    def __init__(self, hass, sensor, name, request_bridge_update, bridge):
        """Initialize the sensor."""
        self.hass = hass
        self.sensor = sensor
        self._name = name
        self.async_request_bridge_update = request_bridge_update
        self.bridge = bridge

        if self.swupdatestate == "readytoinstall":
            err = (
                "Please check for software updates of the %s "
                "sensor in the Philips Hue App."
            )
            _LOGGER.warning(err, self.name)

        self.entity_id = async_generate_entity_id(
            self._entity_id_format, self.name, hass=hass)

    @property
    def device_id(self):
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
        return self.sensor.raw.get('swupdate', {}).get('state')

    @property
    def device_info(self):
        """Return the device info."""
        return {
            'identifiers': {
                (hue.DOMAIN, self.unique_id)
            },
            'name': self.name,
            'manufacturer': self.sensor.manufacturername,
            # productname added in Hue Bridge API 1.24
            # (published 03/05/2018)
            'model': self.sensor.productname or self.sensor.modelid,
            # Not yet exposed as properties in aiohue
            'sw_version': self.sensor.swversion,
            'via_hub': (hue.DOMAIN, self.bridge.api.config.bridgeid),
        }

    async def async_update(self):
        """Synchronize state with bridge."""
        await self.async_request_bridge_update(self.sensor.id)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}
        return attributes


class GenericZLLSensor(GenericHueSensor):

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = super().device_state_attributes
        attributes.update({
            "battery": self.sensor.battery,
            "last_updated": self.sensor.lastupdated,
            "on": self.sensor.on,
            "reachable": self.sensor.reachable,
        })
        return attributes


class HueLightLevel(GenericZLLSensor, Entity):

    _entity_id_format = SENSOR_ENTITY_ID_FORMAT
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

    _entity_id_format = SENSOR_ENTITY_ID_FORMAT
    device_class = DEVICE_CLASS_TEMPERATURE
    unit_of_measurement = TEMP_CELSIUS

    @property
    def state(self):
        """Return the state of the device."""
        return self.sensor.temperature / 100


class HuePresence(GenericZLLSensor, BinarySensorDevice):

    _entity_id_format = BINARY_ENTITY_ID_FORMAT
    device_class = 'presence'
    icon = 'mdi:run'

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.sensor.presence
