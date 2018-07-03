"""
Support for LifeSOS devices to be exposed as sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.lifesos/
"""
import logging

from homeassistant.components.lifesos import (
    LifeSOSBaseSensor, DATA_BASEUNIT, DATA_DEVICES, SIGNAL_PROPERTIES_CHANGED)
from homeassistant.const import (
    CONF_NAME, CONF_ID, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_ILLUMINANCE, TEMP_CELSIUS)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['lifesos']

ATTR_ALARM_HIGH_LIMIT = 'alarm_high_limit'
ATTR_ALARM_LOW_LIMIT = 'alarm_low_limit'
ATTR_CONTROL_HIGH_LIMIT = 'control_high_limit'
ATTR_CONTROL_LOW_LIMIT = 'control_low_limit'
ATTR_EVENT_CODE = 'event_code'
ATTR_HIGH_LIMIT = 'high_limit'
ATTR_LOW_LIMIT = 'low_limit'

UOM_CURRENT = 'A'
UOM_HUMIDITY = '%'
UOM_ILLUMINANCE = 'Lux'


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Set up the LifeSOS sensor devices."""

    device_id = discovery_info[CONF_ID]
    baseunit = hass.data[DATA_BASEUNIT]
    device = baseunit.devices[device_id]

    sensor = LifeSOSSensor(
        baseunit,
        discovery_info[CONF_NAME],
        device)
    async_add_devices([sensor])

    hass.data[DATA_DEVICES][device.device_id] = sensor


class LifeSOSSensor(LifeSOSBaseSensor):
    """Representation of a LifeSOS sensor."""

    def __init__(self, baseunit, name, device):
        super().__init__(baseunit, name, device)

        self._device_class = self._get_device_class_from_device_type()

        # Attach callbacks for device events and property changes
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
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = super().device_state_attributes
        if self._device.control_limit_fields_exist:
            # LS-10/LS-20 have separate alarm and control limits
            attr.update({
                ATTR_ALARM_HIGH_LIMIT: self._device.high_limit,
                ATTR_ALARM_LOW_LIMIT: self._device.low_limit,
                ATTR_CONTROL_HIGH_LIMIT: self._device.control_high_limit,
                ATTR_CONTROL_LOW_LIMIT: self._device.control_low_limit,
            })
        else:
            # LS-30 has only a single high/low limit for alarm and control
            attr.update({
                ATTR_HIGH_LIMIT: self._device.high_limit,
                ATTR_LOW_LIMIT: self._device.low_limit,
            })
        return attr

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        from lifesospy.enums import DeviceType
        if self._device.type in [DeviceType.ACCurrentMeter,
                                 DeviceType.ACCurrentMeter2,
                                 DeviceType.ThreePhaseACMeter]:
            # These have no device class default icon to rely on
            return 'mdi:flash'

        # Use the device class default
        return None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.current_reading

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        from lifesospy.enums import DeviceType
        if self._device.type in [DeviceType.HumidSensor,
                                 DeviceType.HumidSensor2]:
            return UOM_HUMIDITY
        elif self._device.type in [DeviceType.TempSensor,
                                   DeviceType.TempSensor2]:
            return TEMP_CELSIUS
        elif self._device.type in [DeviceType.LightSensor,
                                   DeviceType.LightDetector]:
            return UOM_ILLUMINANCE
        elif self._device.type in [DeviceType.ACCurrentMeter,
                                   DeviceType.ACCurrentMeter2,
                                   DeviceType.ThreePhaseACMeter]:
            return UOM_CURRENT
        return None

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
    def _on_properties_changed(self, device, changes):
        self.async_schedule_update_ha_state()

    def _get_device_class_from_device_type(self):
        # Translate LifeSOS device type to the most appropriate HA class.
        from lifesospy.enums import DeviceType
        if self._device.type in [DeviceType.HumidSensor,
                                 DeviceType.HumidSensor2]:
            return DEVICE_CLASS_HUMIDITY
        elif self._device.type in [DeviceType.TempSensor,
                                   DeviceType.TempSensor2]:
            return DEVICE_CLASS_TEMPERATURE
        elif self._device.type in [DeviceType.LightSensor,
                                   DeviceType.LightDetector]:
            return DEVICE_CLASS_ILLUMINANCE
        elif self._device.type in [DeviceType.ACCurrentMeter,
                                   DeviceType.ACCurrentMeter2,
                                   DeviceType.ThreePhaseACMeter]:
            # No appropriate class for electrical current
            return None

        # Did I forget add support for a device type?
        _LOGGER.debug("Unsupported device type '%s'", self._device.type.name)
        return None
