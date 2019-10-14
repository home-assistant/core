"""Support for Gardena mower."""

import logging
from datetime import timedelta

from homeassistant.core import callback
from homeassistant.components.vacuum import (
    StateVacuumDevice,
    SUPPORT_BATTERY,
    SUPPORT_RETURN_HOME,
    SUPPORT_STATE,
    SUPPORT_STOP,
    SUPPORT_START,
    STATE_PAUSED,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_RETURNING,
    STATE_ERROR,
    ATTR_BATTERY_LEVEL,
)

from . import (
    GARDENA_LOCATION,
    GARDENA_CONFIG,
    CONF_MOWER_DURATION,
    ATTR_NAME,
    ATTR_ACTIVITY,
    ATTR_BATTERY_STATE,
    ATTR_RF_LINK_LEVEL,
    ATTR_RF_LINK_STATE,
    ATTR_SERIAL,
    ATTR_OPERATING_HOURS,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)

SUPPORT_GARDENA = (
    SUPPORT_BATTERY | SUPPORT_RETURN_HOME | SUPPORT_STOP | SUPPORT_START | SUPPORT_STATE
)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Gardena smart mower system."""
    dev = []

    for mower in hass.data[GARDENA_LOCATION].find_device_by_type("MOWER"):
        dev.append(GardenaSmartMower(hass, mower, hass.data[GARDENA_CONFIG]))
    _LOGGER.debug("Adding mower as vacuums %s", dev)
    add_entities(dev, True)


class GardenaSmartMower(StateVacuumDevice):
    """Representation of a Gardena Connected Mower."""

    def __init__(self, hass, mower, config):
        """Initialize the Gardena Connected Mower."""
        self._device = mower
        self._config = config
        self._name = "{}".format(self._device.name)
        self._state = None
        self._error_message = ""

    async def async_added_to_hass(self):
        """Subscribe to events."""
        self._device.add_callback(self.async_update_callback)

    @property
    def should_poll(self) -> bool:
        """No polling needed for a vacuum."""
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
        _LOGGER.debug("Mower has state %s", state)
        if state in ["WARNING", "ERROR", "UNAVAILABLE"]:
            _LOGGER.debug("Mower has an error")
            self._state = STATE_ERROR
            self._error_message = self._device.last_error_code
        else:
            _LOGGER.debug("Getting mower state")
            activity = self._device.activity
            _LOGGER.debug("Mower has activity %s", activity)
            if activity == "PAUSED":
                self._state = STATE_PAUSED
            elif activity in [
                "OK_CUTTING",
                "OK_CUTTING_TIMER_OVERRIDDEN",
                "OK_LEAVING",
            ]:
                self._state = STATE_CLEANING
            elif activity == "OK_SEARCHING":
                self._state = STATE_RETURNING
            elif activity in [
                "OK_CHARGING",
                "PARKED_TIMER",
                "PARKED_PARK_SELECTED",
                "PARKED_AUTOTIMER",
            ]:
                self._state = STATE_DOCKED
            elif activity == "NONE":
                self._state = None
                _LOGGER.debug("Mower has no activity")

    @property
    def name(self):
        """Return the name of the device."""
        return self._device.name

    @property
    def supported_features(self):
        """Flag lawn mower robot features that are supported."""
        return SUPPORT_GARDENA

    @property
    def battery_level(self):
        """Return the battery level of the lawn mower."""
        return self._device.battery_level

    @property
    def state(self):
        """Return the status of the lawn mower."""
        return self._state

    @property
    def available(self):
        """Return True if the device is available."""
        return self._device.state != "UNAVAILABLE"

    def error(self):
        """Return the error message."""
        if self._state == STATE_ERROR:
            return self._error_message
        return ""

    @property
    def device_state_attributes(self):
        """Return the state attributes of the lawn mower."""
        return {
            ATTR_NAME: self._name,
            ATTR_ACTIVITY: self._device.activity,
            ATTR_BATTERY_LEVEL: self._device.battery_level,
            ATTR_BATTERY_STATE: self._device.battery_state,
            ATTR_RF_LINK_LEVEL: self._device.rf_link_level,
            ATTR_RF_LINK_STATE: self._device.rf_link_state,
            ATTR_SERIAL: self._device.serial,
            ATTR_OPERATING_HOURS: self._device.operating_hours,
        }

    def start(self):
        """Start the mower."""
        self.turn_on()

    def turn_on(self):
        """Start cleaning or resume mowing."""
        duration = str(int(self._config[CONF_MOWER_DURATION]) * 60)
        self._device.start_seconds_to_override(duration)

    def turn_off(self):
        """Stop mowing."""
        self._device.park_until_next_task()

    def return_to_base(self, **kwargs):
        """Set the lawn mower to return to the dock."""
        self.turn_off()

    def stop(self, **kwargs):
        """Stop the lawn mower."""
        self.turn_off()
