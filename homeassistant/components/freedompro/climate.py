"""Support for Freedompro climate."""
import json

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
    TEMP_CELSIUS,
    ClimateEntity,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN
from .utils import putState


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro climate."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    devices = [
        Device(hass, api_key, device, coordinator)
        for device in coordinator.data
        if device["type"] == "thermostat"
    ]

    async_add_entities(devices, False)


class Device(CoordinatorEntity, ClimateEntity):
    """Representation of an Freedompro climate."""

    def __init__(self, hass, api_key, device, coordinator):
        """Initialize the Freedompro climate."""
        super().__init__(coordinator)
        self._hass = hass
        self._api_key = api_key
        self._name = device["name"]
        self._uid = device["uid"]
        self._type = device["type"]
        self._characteristics = device["characteristics"]
        self._mode = 1
        self._currentTemperature = 0
        self._targetTemperature = 0

    @property
    def name(self):
        """Return the name of the Freedompro climate."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique identifier for this climate."""
        return self._uid

    @property
    def supported_features(self):
        """Supported features for lock."""
        support = SUPPORT_TARGET_TEMPERATURE
        return support

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        device = next(
            (device for device in self.coordinator.data if device["uid"] == self._uid),
            None,
        )
        if device is not None:
            if "state" in device:
                state = device["state"]
                if "heatingCoolingState" in state:
                    self._mode = state["heatingCoolingState"]
        if self._mode == 0:
            return "off"
        if self._mode == 1:
            return "heat"
        if self._mode == 2:
            return "cool"

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return [HVAC_MODE_OFF, HVAC_MODE_COOL, HVAC_MODE_HEAT]

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        return 30

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        return 10

    @property
    def current_temperature(self):
        """Return the status of the current_temperature."""
        device = next(
            (device for device in self.coordinator.data if device["uid"] == self._uid),
            None,
        )
        if device is not None:
            if "state" in device:
                state = device["state"]
                if "currentTemperature" in state:
                    self._currentTemperature = state["currentTemperature"]
        return self._currentTemperature

    @property
    def target_temperature(self):
        """Return the status of the target_temperature."""
        device = next(
            (device for device in self.coordinator.data if device["uid"] == self._uid),
            None,
        )
        if device is not None:
            if "state" in device:
                state = device["state"]
                if "targetTemperature" in state:
                    self._targetTemperature = state["targetTemperature"]
        return self._targetTemperature

    async def async_set_hvac_mode(self, hvac_mode):
        """Async function to set mode to climate."""
        if hvac_mode == "off":
            self._mode = 0
        if hvac_mode == "heat":
            self._mode = 1
        if hvac_mode == "cool":
            self._mode = 2
        payload = {"heatingCoolingState": self._mode}
        payload = json.dumps(payload)
        await putState(self._hass, self._api_key, self._uid, payload)
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs):
        """Async function to set temperature to climate."""
        payload = {}
        if ATTR_TEMPERATURE in kwargs:
            self._targetTemperature = kwargs[ATTR_TEMPERATURE]
            payload["targetTemperature"] = self._targetTemperature
        payload = json.dumps(payload)
        await putState(self._hass, self._api_key, self._uid, payload)
        await self.coordinator.async_request_refresh()
