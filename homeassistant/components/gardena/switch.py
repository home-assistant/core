"""Support for Gardena switch (Power control, water control, smart irrigation control)."""

import logging

from homeassistant.core import callback
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import ATTR_BATTERY_LEVEL

from . import (
    GARDENA_LOCATION,
    GARDENA_CONFIG,
    CONF_SMART_IRRIGATION_DURATION,
    CONF_SMART_WATERING,
    ATTR_LAST_ERRORS,
    ATTR_ACTIVITY,
    ATTR_BATTERY_STATE,
    ATTR_RF_LINK_LEVEL,
    ATTR_RF_LINK_STATE,
    ATTR_SERIAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the switches plateform."""
    dev = []

    for water_control in hass.data[GARDENA_LOCATION].find_device_by_type(
        "WATER_CONTROL"
    ):
        dev.append(GardenaSmartWaterControl(water_control, hass.data[GARDENA_CONFIG]))
    for power_switch in hass.data[GARDENA_LOCATION].find_device_by_type("POWER_SOCKET"):
        dev.append(GardenaPowerSocket(power_switch, hass.data[GARDENA_CONFIG]))
    for smart_irrigation in hass.data[GARDENA_LOCATION].find_device_by_type(
        "SMART_IRRIGATION_CONTROL"
    ):
        for valve in smart_irrigation.valves.values():
            dev.append(
                GardenaSmartIrrigationControl(
                    smart_irrigation, valve, hass.data[GARDENA_CONFIG]
                )
            )
    _LOGGER.debug(
        "Adding water control, power socket and smart irrigation control as switch %s",
        dev,
    )
    add_entities(dev, True)


class GardenaSmartWaterControl(SwitchDevice):
    """Representation of a Gardena Smart Water Control."""

    def __init__(self, wc, config):
        """Initialize the Gardena Smart Water Control."""
        self._device = wc
        self._config = config
        self._name = f"{self._device.name}"
        self._state = None
        self._error_message = ""

    async def async_added_to_hass(self):
        """Subscribe to events."""
        self._device.add_callback(self.async_update_callback)

    @property
    def should_poll(self) -> bool:
        """No polling needed for a water valve."""
        return False

    @callback
    def async_update_callback(self, device):
        """Call update for Home Assistant when the device is updated."""
        self.schedule_update_ha_state(True)

    async def async_update(self):
        """Update the states of Gardena devices."""
        _LOGGER.debug("Running Gardena update")
        # Managing state
        state = self._device.valve_state
        _LOGGER.debug("Water control has state %s", state)
        if state in ["WARNING", "ERROR", "UNAVAILABLE"]:
            _LOGGER.debug("Water control has an error")
            self._state = False
            self._error_message = self._device.last_error_code
        else:
            _LOGGER.debug("Getting water control state")
            activity = self._device.valve_activity
            self._error_message = ""
            _LOGGER.debug("Water control has activity %s", activity)
            if activity == "CLOSED":
                self._state = False
            elif activity in ["MANUAL_WATERING", "SCHEDULED_WATERING"]:
                self._state = True
            else:
                _LOGGER.debug("Water control has none activity")

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return true if it is on."""
        return self._state

    @property
    def available(self):
        """Return True if the device is available."""
        return self._device.valve_state != "UNAVAILABLE"

    def error(self):
        """Return the error message."""
        return self._error_message

    @property
    def device_state_attributes(self):
        """Return the state attributes of the water valve."""
        return {
            ATTR_ACTIVITY: self._device.valve_activity,
            ATTR_BATTERY_LEVEL: self._device.battery_level,
            ATTR_BATTERY_STATE: self._device.battery_state,
            ATTR_RF_LINK_LEVEL: self._device.rf_link_level,
            ATTR_RF_LINK_STATE: self._device.rf_link_state,
            ATTR_SERIAL: self._device.serial,
            ATTR_LAST_ERRORS: self._error_message,
        }

    def turn_on(self, **kwargs):
        """Start watering."""
        duration = 3600
        if self._config[CONF_SMART_WATERING]:
            duration = str(int(self._config[CONF_SMART_WATERING]) * 60)
        self._device.start_seconds_to_override(duration)

    def turn_off(self, **kwargs):
        """Stop watering."""
        self._device.stop_until_next_task()


class GardenaPowerSocket(SwitchDevice):
    """Representation of a Gardena Power Socket."""

    def __init__(self, ps, config):
        """Initialize the Gardena Power Socket."""
        self._device = ps
        self._config = config
        self._name = f"{self._device.name}"
        self._state = None
        self._error_message = ""

    async def async_added_to_hass(self):
        """Subscribe to events."""
        self._device.add_callback(self.async_update_callback)

    @property
    def should_poll(self) -> bool:
        """No polling needed for a power socket."""
        return False

    @callback
    def async_update_callback(self, device):
        """Call update for Home Assistant when the device is updated."""
        self.schedule_update_ha_state(True)

    async def async_update(self):
        """Update the states of Gardena devices."""
        _LOGGER.debug("Running Gardena update")
        # Managing state
        state = self._device.state
        _LOGGER.debug("Power socket has state %s", state)
        if state in ["WARNING", "ERROR", "UNAVAILABLE"]:
            _LOGGER.debug("Power socket has an error")
            self._state = False
            self._error_message = self._device.last_error_code
        else:
            _LOGGER.debug("Getting Power socket state")
            activity = self._device.activity
            self._error_message = ""
            _LOGGER.debug("Power socket has activity %s", activity)
            if activity == "OFF":
                self._state = False
            elif activity in ["FOREVER_ON", "TIME_LIMITED_ON", "SCHEDULED_ON"]:
                self._state = True
            else:
                _LOGGER.debug("Power socket has none activity")

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return true if it is on."""
        return self._state

    @property
    def available(self):
        """Return True if the device is available."""
        return self._device.state != "UNAVAILABLE"

    def error(self):
        """Return the error message."""
        return self._error_message

    @property
    def device_state_attributes(self):
        """Return the state attributes of the power switch."""
        return {
            ATTR_ACTIVITY: self._device.activity,
            ATTR_RF_LINK_LEVEL: self._device.rf_link_level,
            ATTR_RF_LINK_STATE: self._device.rf_link_state,
            ATTR_SERIAL: self._device.serial,
            ATTR_LAST_ERRORS: self._error_message,
        }

    def turn_on(self, **kwargs):
        """Start watering."""
        self._device.start_override()

    def turn_off(self, **kwargs):
        """Stop watering."""
        self._device.stop_until_next_task()


class GardenaSmartIrrigationControl(SwitchDevice):
    """Representation of a Gardena Smart Irrigation Control."""

    def __init__(self, sic, valve, config):
        """Initialize the Gardena Smart Irrigation Control."""
        self._device = valve
        self._sic = sic
        self._config = config
        self._name = f'{self._sic.name} - {self._device["name"]}'
        self._state = None
        self._error_message = ""

    async def async_added_to_hass(self):
        """Subscribe to events."""
        self._sic.add_callback(self.async_update_callback)

    @property
    def should_poll(self) -> bool:
        """No polling needed for a smart irrigation control."""
        return False

    @callback
    def async_update_callback(self, device):
        """Call update for Home Assistant when the device is updated."""
        self.schedule_update_ha_state(True)

    async def async_update(self):
        """Update the states of Gardena devices."""
        _LOGGER.debug("Running Gardena update")
        # Managing state
        state = self._device["state"]
        _LOGGER.debug("Valve has state %s", state)
        if state in ["WARNING", "ERROR", "UNAVAILABLE"]:
            _LOGGER.debug("Valve has an error")
            self._state = False
            self._error_message = self._device["last_error_code"]
        else:
            _LOGGER.debug("Getting Valve state")
            activity = self._device["activity"]
            self._error_message = ""
            _LOGGER.debug("Valve has activity %s", activity)
            if activity == "OFF":
                self._state = False
            elif activity in ["FOREVER_ON", "TIME_LIMITED_ON", "SCHEDULED_ON"]:
                self._state = True
            else:
                _LOGGER.debug("Valve has none activity")

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return true if it is on."""
        return self._state

    @property
    def available(self):
        """Return True if the device is available."""
        return self._device["state"] != "UNAVAILABLE"

    def error(self):
        """Return the error message."""
        return self._error_message

    @property
    def device_state_attributes(self):
        """Return the state attributes of the smart irrigation control."""
        return {
            ATTR_ACTIVITY: self._device["activity"],
            ATTR_RF_LINK_LEVEL: self._sic.rf_link_level,
            ATTR_RF_LINK_STATE: self._sic.rf_link_state,
            ATTR_SERIAL: self._sic.serial,
            ATTR_LAST_ERRORS: self._error_message,
        }

    def turn_on(self, **kwargs):
        """Start watering."""
        duration = 3600
        if self._config[CONF_SMART_IRRIGATION_DURATION]:
            duration = str(int(self._config[CONF_SMART_IRRIGATION_DURATION]) * 60)
        self._device.start_seconds_to_override(duration, self._device["id"])

    def turn_off(self, **kwargs):
        """Stop watering."""
        self._device.stop_until_next_task(self._device["id"])
