"""Support for AVM Fritz!Box smarthome switch devices."""
import requests

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_DEVICES,
    ENERGY_KILO_WATT_HOUR,
    TEMP_CELSIUS,
)

from .const import (
    ATTR_STATE_DEVICE_LOCKED,
    ATTR_STATE_LOCKED,
    ATTR_TEMPERATURE_UNIT,
    ATTR_TOTAL_CONSUMPTION,
    ATTR_TOTAL_CONSUMPTION_UNIT,
    CONF_CONNECTIONS,
    DOMAIN as FRITZBOX_DOMAIN,
    LOGGER,
)

ATTR_TOTAL_CONSUMPTION_UNIT_VALUE = ENERGY_KILO_WATT_HOUR


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Fritzbox smarthome switch from config_entry."""
    entities = []
    devices = hass.data[FRITZBOX_DOMAIN][CONF_DEVICES]
    fritz = hass.data[FRITZBOX_DOMAIN][CONF_CONNECTIONS][config_entry.entry_id]

    for device in await hass.async_add_executor_job(fritz.get_devices):
        if device.has_switch and device.ain not in devices:
            entities.append(FritzboxSwitch(device, fritz))
            devices.add(device.ain)

    async_add_entities(entities)


class FritzboxSwitch(SwitchDevice):
    """The switch class for Fritzbox switches."""

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
    def available(self):
        """Return if switch is available."""
        return self._device.present

    @property
    def name(self):
        """Return the name of the device."""
        return self._device.name

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._device.switch_state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._device.set_switch_state_on()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._device.set_switch_state_off()

    def update(self):
        """Get latest data and states from the device."""
        try:
            self._device.update()
        except requests.exceptions.HTTPError as ex:
            LOGGER.warning("Fritzhome connection error: %s", ex)
            self._fritz.login()

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attrs = {}
        attrs[ATTR_STATE_DEVICE_LOCKED] = self._device.device_lock
        attrs[ATTR_STATE_LOCKED] = self._device.lock

        if self._device.has_powermeter:
            attrs[
                ATTR_TOTAL_CONSUMPTION
            ] = f"{((self._device.energy or 0.0) / 1000):.3f}"
            attrs[ATTR_TOTAL_CONSUMPTION_UNIT] = ATTR_TOTAL_CONSUMPTION_UNIT_VALUE
        if self._device.has_temperature_sensor:
            attrs[ATTR_TEMPERATURE] = str(
                self.hass.config.units.temperature(
                    self._device.temperature, TEMP_CELSIUS
                )
            )
            attrs[ATTR_TEMPERATURE_UNIT] = self.hass.config.units.temperature_unit
        return attrs

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self._device.power / 1000
