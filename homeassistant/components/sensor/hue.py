"""
This component provides sensor support for the Philips Hue system.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.hue/
"""
import asyncio
from datetime import timedelta
import logging
import async_timeout

from aiohue.sensors import (ZGP_SWITCH_BUTTON_1, ZGP_SWITCH_BUTTON_2, ZGP_SWITCH_BUTTON_3,
                            ZGP_SWITCH_BUTTON_4, ZLL_SWITCH_BUTTON_1_LONG_RELEASED,
                            ZLL_SWITCH_BUTTON_1_SHORT_RELEASED, ZLL_SWITCH_BUTTON_2_LONG_RELEASED,
                            ZLL_SWITCH_BUTTON_2_SHORT_RELEASED, ZLL_SWITCH_BUTTON_3_LONG_RELEASED,
                            ZLL_SWITCH_BUTTON_3_SHORT_RELEASED, ZLL_SWITCH_BUTTON_4_LONG_RELEASED,
                            ZLL_SWITCH_BUTTON_4_SHORT_RELEASED, TYPE_CLIP_GENERICSTATUS,
                            TYPE_CLIP_HUMIDITY, TYPE_CLIP_LIGHTLEVEL, TYPE_CLIP_TEMPERATURE,
                            TYPE_ZGP_SWITCH, TYPE_ZLL_SWITCH, TYPE_ZLL_LIGHTLEVEL,
                            TYPE_ZLL_TEMPERATURE, TYPE_CLIP_SWITCH)

import homeassistant.components.hue as hue
from homeassistant.components.hue.const import (ATTR_DARK, ATTR_DAYLIGHT, ICON_REMOTE,
                                                UOM_HUMIDITY, UOM_ILLUMINANCE)
from homeassistant.components.sensor import (DEVICE_CLASS_HUMIDITY,
                                             DEVICE_CLASS_ILLUMINANCE,
                                             DEVICE_CLASS_TEMPERATURE)
from homeassistant.const import (ATTR_BATTERY_LEVEL, TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['hue']
SCAN_INTERVAL = timedelta(seconds=1)

ALL_SENSORS = [TYPE_CLIP_GENERICSTATUS, TYPE_CLIP_HUMIDITY, TYPE_CLIP_LIGHTLEVEL,
               TYPE_CLIP_SWITCH, TYPE_CLIP_TEMPERATURE, TYPE_CLIP_HUMIDITY, TYPE_ZGP_SWITCH,
               TYPE_ZLL_LIGHTLEVEL, TYPE_ZLL_SWITCH, TYPE_ZLL_TEMPERATURE]
HUE_SENSORS = [TYPE_ZGP_SWITCH, TYPE_ZLL_LIGHTLEVEL, TYPE_ZLL_SWITCH, TYPE_ZLL_TEMPERATURE]

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Old way of setting up Hue.

    Can only be called when a user accidentally mentions hue platform in their
    config. But even in that case it would have been ignored.
    """
    pass


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the Hue sensors from a config entry."""
    bridge = hass.data[hue.DOMAIN][config_entry.data['host']]
    cur_sensors = {}

    # Hue updates all devices via a single API call.
    #
    # If we call a service to update 2 devices, we only want the API to be
    # called once.
    #
    # The throttle decorator will return right away if a call is currently
    # in progress. This means that if we are updating 2 devices, the first one
    # is in the update method, the second one will skip it and assume the
    # update went through and updates it's data, not good!
    #
    # The current mechanism will make sure that all devices will wait till
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

        We keep track of the sensors that are waiting for the request to finish.
        When new data comes in, we'll trigger an update for all non-waiting
        sensors. This covers the case where a service is called to modify 2
        sensors but in the meanwhile some other sensor has changed too.
        """
        nonlocal progress

        progress_set = sensor_progress
        progress_set.add(object_id)

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
            hass, bridge, async_add_devices, request_update,
            cur_sensors, sensor_progress
        ))

        await asyncio.wait(tasks)

    await update_bridge()


async def async_update_items(hass, bridge, async_add_devices,
                             request_bridge_update, current,
                             progress_waiting):
    """Update sensors from the bridge."""
    import aiohue
    allow_clip_sensors = bridge.allow_clip_sensors

    api = bridge.api.sensors

    try:
        with async_timeout.timeout(4):
            await api.update()
    except (asyncio.TimeoutError, aiohue.AiohueException):
        if not bridge.available:
            return

        _LOGGER.error('Unable to reach bridge %s', bridge.host)
        bridge.available = False

        for sensor_id, sensor in current.items():
            if sensor_id not in progress_waiting:
                sensor.async_schedule_update_ha_state()

        return

    if not bridge.available:
        _LOGGER.info('Reconnected to bridge %s', bridge.host)
        bridge.available = True

    new_sensors = []

    if allow_clip_sensors:
        allowed_sensor_types = ALL_SENSORS
    else:
        allowed_sensor_types = HUE_SENSORS

    for item_id in api:
        sensor = api[item_id]
        if sensor.type in allowed_sensor_types:
            if item_id not in current:
                current[item_id] = create_sensor(
                    sensor, request_bridge_update, bridge)

                new_sensors.append(current[item_id])
                _LOGGER.info('Added new Hue sensor: %s (Type: %s)',
                             sensor.name, sensor.type)
            elif item_id not in progress_waiting:
                current[item_id].async_schedule_update_ha_state()

    if new_sensors:
        async_add_devices(new_sensors)


class HueSensor(Entity):
    """Base class representing a Hue sensor.
    Contains properties and methods common to all Hue sensors."""
    def __init__(self, sensor, request_bridge_update, bridge):
        self.sensor = sensor
        self.async_request_bridge_update = request_bridge_update
        self.bridge = bridge
        self._hue_last_updated = getattr(self.sensor, 'lastupdated', None)

    @property
    def name(self):
        """Return the name of the Hue sensor."""
        return self.sensor.name

    @property
    def available(self):
        """Reachable returns true if the Hue sensor is available."""
        return self.sensor.reachable

    @property
    def unique_id(self):
        """Return the unique id of the Hue sensor."""
        return self.sensor.uniqueid

    async def async_update(self):
        """Synchronize state with bridge."""
        await self.async_request_bridge_update(self.sensor.id)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}
        if self.sensor.battery is not None:
            attributes[ATTR_BATTERY_LEVEL] = self.sensor.battery
        return attributes


class CLIPGenericStatus(HueSensor):

    @property
    def state(self):
        """Return the state of the CLIP sensor."""
        return self.sensor.status


class CLIPHumidity(HueSensor):

    @property
    def state(self):
        """Return the state of the CLIP sensor."""
        return self.sensor.humidity

    @property
    def device_class(self):
        """Return the device class of the CLIP sensor."""
        return DEVICE_CLASS_HUMIDITY

    @property
    def unit_of_measurement(self):
        """Return the uom of the CLIP sensor."""
        return UOM_HUMIDITY


class CLIPLightLevel(HueSensor):

    @property
    def state(self):
        """Return the state of the CLIP sensor."""
        return self.sensor.lightlevel

    @property
    def device_class(self):
        """Return the device class of the CLIP sensor."""
        return DEVICE_CLASS_ILLUMINANCE

    @property
    def unit_of_measurement(self):
        """Return the uom of the CLIP sensor."""
        return UOM_ILLUMINANCE


class CLIPSwitch(HueSensor):

    @property
    def icon(self):
        """Return the remote icon."""
        return ICON_REMOTE

    @property
    def state(self):
        """Return the switch's buttonevent if the lastupdated variable changed."""
        current_time = self.sensor.lastupdated
        if current_time == self._hue_last_updated:
            return None
        else:
            self._hue_last_updated = current_time
            return self.sensor.buttonevent


class HueTemperature(HueSensor):

    @property
    def state(self):
        """Return the state of the CLIP sensor."""
        return round(self.sensor.temperature / 100, 1)

    @property
    def device_class(self):
        """Return the device class of the CLIP sensor."""
        return DEVICE_CLASS_TEMPERATURE

    @property
    def unit_of_measurement(self):
        """Return the uom of the CLIP sensor."""
        return TEMP_CELSIUS


class ZGPSwitch(HueSensor):
    """Class representing a ZGP (Hue Tap) Switch."""

    @property
    def icon(self):
        """Return the remote icon."""
        return ICON_REMOTE

    @property
    def state(self):
        """Return the switch's buttonevent if the lastupdated variable changed."""
        current_time = self.sensor.lastupdated
        if current_time == self._hue_last_updated:
            return None
        else:
            self._hue_last_updated = current_time
            if self.sensor.buttonevent == ZGP_SWITCH_BUTTON_1:
                return '1_click'
            elif self.sensor.buttonevent == ZGP_SWITCH_BUTTON_2:
                return '2_click'
            elif self.sensor.buttonevent == ZGP_SWITCH_BUTTON_3:
                return '3_click'
            elif self.sensor.buttonevent == ZGP_SWITCH_BUTTON_4:
                return '4_click'


class ZLLLightLevel(HueSensor):

    @property
    def state(self):
        """Return the state of the Hue sensor."""
        return pow(10, (self.sensor.lightlevel - 1) / 10000)

    @property
    def device_class(self):
        """Return the device class of the Hue sensor."""
        return DEVICE_CLASS_ILLUMINANCE

    @property
    def unit_of_measurement(self):
        """Return the uom of the Hue sensor."""
        return UOM_ILLUMINANCE

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}
        attributes[ATTR_BATTERY_LEVEL] = self.sensor.battery
        attributes[ATTR_DARK] = self.sensor.dark
        attributes[ATTR_DAYLIGHT] = self.sensor.daylight
        return attributes


class ZLLSwitch(HueSensor):
    """Class representing a ZLL (Hue Wireless Dimmer) Switch."""

    @property
    def icon(self):
        """Return the remote icon."""
        return ICON_REMOTE

    @property
    def state(self):
        """Return the switch's buttonevent if the lastupdated variable changed.
        If lastupdated hasn't changed, reset the sensor's state to None."""
        current_time = self.sensor.lastupdated
        if current_time == self._hue_last_updated:
            return None
        else:
            self._hue_last_updated = current_time
            if self.sensor.buttonevent == ZLL_SWITCH_BUTTON_1_SHORT_RELEASED:
                return '1_click'
            elif self.sensor.buttonevent == ZLL_SWITCH_BUTTON_1_LONG_RELEASED:
                return '1_hold'
            elif self.sensor.buttonevent == ZLL_SWITCH_BUTTON_2_SHORT_RELEASED:
                return '2_click'
            elif self.sensor.buttonevent == ZLL_SWITCH_BUTTON_2_LONG_RELEASED:
                return '2_hold'
            elif self.sensor.buttonevent == ZLL_SWITCH_BUTTON_3_SHORT_RELEASED:
                return '3_click'
            elif self.sensor.buttonevent == ZLL_SWITCH_BUTTON_3_LONG_RELEASED:
                return '3_hold'
            elif self.sensor.buttonevent == ZLL_SWITCH_BUTTON_4_SHORT_RELEASED:
                return '4_click'
            elif self.sensor.buttonevent == ZLL_SWITCH_BUTTON_4_LONG_RELEASED:
                return '4_hold'


def create_sensor(sensor, request_bridge_update, bridge):
    sensor_type = sensor.type
    if sensor_type == TYPE_CLIP_GENERICSTATUS:
        return CLIPGenericStatus(sensor, request_bridge_update, bridge)
    elif sensor_type == TYPE_CLIP_HUMIDITY:
        return CLIPHumidity(sensor, request_bridge_update, bridge)
    elif sensor_type == TYPE_CLIP_LIGHTLEVEL:
        return CLIPLightLevel(sensor, request_bridge_update, bridge)
    elif sensor_type == TYPE_CLIP_SWITCH:
        return CLIPSwitch(sensor, request_bridge_update, bridge)
    elif sensor_type in [TYPE_CLIP_TEMPERATURE, TYPE_ZLL_TEMPERATURE]:
        return HueTemperature(sensor, request_bridge_update, bridge)
    elif sensor_type == TYPE_ZGP_SWITCH:
        return ZGPSwitch(sensor, request_bridge_update, bridge)
    elif sensor_type == TYPE_ZLL_LIGHTLEVEL:
        return ZLLLightLevel(sensor, request_bridge_update, bridge)
    elif sensor_type == TYPE_ZLL_SWITCH:
        return ZLLSwitch(sensor, request_bridge_update, bridge)
