"""
Support for LifeSOS devices to be exposed as binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.lifesos/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.lifesos import (
    LifeSOSBaseSensor, DATA_BASEUNIT, DATA_DEVICES, SIGNAL_PROPERTIES_CHANGED,
    CONF_TRIGGER_DURATION)
from homeassistant.const import CONF_NAME, CONF_ID
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['lifesos']


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Set up the LifeSOS binary sensor devices."""

    device_id = discovery_info[CONF_ID]
    baseunit = hass.data[DATA_BASEUNIT]
    device = baseunit.devices[device_id]

    binary_sensor = LifeSOSBinarySensor(
        baseunit,
        discovery_info[CONF_NAME],
        device,
        discovery_info[CONF_TRIGGER_DURATION])
    async_add_devices([binary_sensor])

    hass.data[DATA_DEVICES][device.device_id] = binary_sensor


class LifeSOSBinarySensor(LifeSOSBaseSensor, BinarySensorDevice):
    """Representation of a LifeSOS binary sensor."""

    def __init__(self, baseunit, name, device, trigger_duration):
        from lifesospy.enums import DeviceType

        super().__init__(baseunit, name, device)

        self._trigger_duration = trigger_duration
        self._device_class = self._get_device_class_from_device_type()
        self._auto_reset_handle = None

        # Only the magnet sensor maintains an open/close state;
        # the other types require a trigger event to occur
        if self._device.type == DeviceType.DoorMagnet:
            self._is_on = not device.is_closed
        else:
            self._is_on = False

        # Attach callbacks for device events and property changes
        device.on_event = self._on_event
        device.on_properties_changed = self._on_properties_changed

    @property
    def available(self):
        """Return True if device is available."""
        return self._baseunit.is_connected

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return self._device_class

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._is_on

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_PROPERTIES_CHANGED,
            self.handle_properties_changed)

    @callback
    def handle_properties_changed(self, changes):
        """When the base unit connection state changes, update availability."""
        from lifesospy.baseunit import BaseUnit

        do_update = False
        for change in changes:
            if change.name == BaseUnit.PROP_IS_CONNECTED:
                do_update = True
        if do_update:
            self.async_schedule_update_ha_state()

    @callback
    def _on_event(self, device, event_code):
        from lifesospy.enums import DeviceEventCode as EventCode

        # Open / Close events are for Door Magnet only
        if event_code == EventCode.Open:
            self._is_on = True
        elif event_code == EventCode.Close:
            self._is_on = False

        # Trigger events are one-off; set state to on and start a delay
        # timer to automatically turn it off after a short period
        elif event_code == EventCode.Trigger:
            if not self._is_on:
                self._is_on = True
            else:
                # Still on with auto reset callback pending; cancel it
                # so that we can reschedule for a later time
                self._auto_reset_handle.cancel()
            self._auto_reset_handle = self.hass.loop.call_later(
                self._trigger_duration, self._auto_reset)

        self.async_schedule_update_ha_state()

    @callback
    def _on_properties_changed(self, device, changes):
        self.async_schedule_update_ha_state()

    @callback
    def _auto_reset(self):
        self._is_on = False
        self.async_schedule_update_ha_state()

    def _get_device_class_from_device_type(self):
        # Translate LifeSOS device type to the most appropriate HA class.
        from lifesospy.enums import DeviceType
        if self._device.type in {DeviceType.FloodDetector,
                                 DeviceType.FloodDetector2}:
            return 'moisture'
        elif self._device.type == DeviceType.MedicalButton:
            return 'safety'
        elif self._device.type in {DeviceType.AnalogSensor,
                                   DeviceType.AnalogSensor2}:
            return None
        elif self._device.type == DeviceType.SmokeDetector:
            return 'smoke'
        elif self._device.type in {DeviceType.PressureSensor,
                                   DeviceType.PressureSensor2}:
            return 'motion'
        elif self._device.type in {DeviceType.CODetector,
                                   DeviceType.CO2Sensor,
                                   DeviceType.CO2Sensor2,
                                   DeviceType.GasDetector}:
            return 'gas'
        elif self._device.type == DeviceType.DoorMagnet:
            return 'door'
        elif self._device.type == DeviceType.VibrationSensor:
            return 'vibration'
        elif self._device.type == DeviceType.PIRSensor:
            return 'motion'
        elif self._device.type == DeviceType.GlassBreakDetector:
            return 'window'

        # Did I forget add support for a device type?
        _LOGGER.debug("Unsupported device type '%s'", self._device.type.name)
        return None
