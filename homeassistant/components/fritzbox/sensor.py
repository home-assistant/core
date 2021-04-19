"""Support for AVM Fritz!Box smarthome temperature sensor only devices."""
import requests

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONF_DEVICES,
    DEVICE_CLASS_BATTERY,
    PERCENTAGE,
    TEMP_CELSIUS,
)

from .const import (
    ATTR_STATE_DEVICE_LOCKED,
    ATTR_STATE_LOCKED,
    CONF_CONNECTIONS,
    DOMAIN as FRITZBOX_DOMAIN,
    LOGGER,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Fritzbox smarthome sensor from config_entry."""
    entities = []
    devices = hass.data[FRITZBOX_DOMAIN][CONF_DEVICES]
    fritz = hass.data[FRITZBOX_DOMAIN][CONF_CONNECTIONS][config_entry.entry_id]

    for device in await hass.async_add_executor_job(fritz.get_devices):
        if (
            device.has_temperature_sensor
            and not device.has_switch
            and not device.has_thermostat
            and device.ain not in devices
        ):
            entities.append(FritzBoxTempSensor(device, fritz))
            devices.add(device.ain)

        if device.battery_level is not None:
            entities.append(FritzBoxBatterySensor(device, fritz))
            devices.add(f"{device.ain}_battery")

    async_add_entities(entities)


class FritzBoxBatterySensor(SensorEntity):
    """The entity class for Fritzbox battery sensors."""

    def __init__(self, device, fritz):
        """Initialize the sensor."""
        self._device = device
        self._fritz = fritz

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self.name,
            "identifiers": {(FRITZBOX_DOMAIN, self._device.ain)},
            "manufacturer": self._device.manufacturer,
            "model": self._device.productname,
            "sw_version": self._device.fw_version,
        }

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return f"{self._device.ain}_battery"

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self._device.name} Battery"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.battery_level

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return PERCENTAGE

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_BATTERY


class FritzBoxTempSensor(SensorEntity):
    """The entity class for Fritzbox temperature sensors."""

    def __init__(self, device, fritz):
        """Initialize the switch."""
        self._device = device
        self._fritz = fritz

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self.name,
            "identifiers": {(FRITZBOX_DOMAIN, self._device.ain)},
            "manufacturer": self._device.manufacturer,
            "model": self._device.productname,
            "sw_version": self._device.fw_version,
        }

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return self._device.ain

    @property
    def name(self):
        """Return the name of the device."""
        return self._device.name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.temperature

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    def update(self):
        """Get latest data and states from the device."""
        try:
            self._device.update()
        except requests.exceptions.HTTPError as ex:
            LOGGER.warning("Fritzhome connection error: %s", ex)
            self._fritz.login()

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        attrs = {
            ATTR_STATE_DEVICE_LOCKED: self._device.device_lock,
            ATTR_STATE_LOCKED: self._device.lock,
        }
        return attrs
