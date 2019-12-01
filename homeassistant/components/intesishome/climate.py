"""
Support for IntesisHome Smart AC Controllers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/intesishome/
"""
import logging
from datetime import timedelta
import voluptuous as vol
from pyintesishome import IntesisHome

import homeassistant.helpers.config_validation as cv

from homeassistant.const import CONF_DEVICE
from homeassistant.components import persistent_notification
from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession


REQUIREMENTS = ["pyintesishome==1.1"]

_LOGGER = logging.getLogger(__name__)

IH_DEVICE_INTESISHOME = "IntesisHome"
IH_DEVICE_AIRCONWITHME = "airconwithme"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DEVICE, default=IH_DEVICE_INTESISHOME): vol.In(
            [IH_DEVICE_AIRCONWITHME, IH_DEVICE_INTESISHOME]
        ),
    }
)

# Return cached results if last scan time was less than this value.
# If a persistent connection is established for the controller, changes to
# values are in realtime.
SCAN_INTERVAL = timedelta(seconds=300)

IH_SWING_WIDGET = 42

MAP_OPERATION_MODE = {
    "auto": HVAC_MODE_HEAT_COOL,
    "cool": HVAC_MODE_COOL,
    "dry": HVAC_MODE_DRY,
    "fan": HVAC_MODE_FAN_ONLY,
    "heat": HVAC_MODE_HEAT,
    "off": HVAC_MODE_OFF,
}


MAP_STATE_ICONS = {
    HVAC_MODE_COOL: "mdi:snowflake",
    HVAC_MODE_DRY: "mdi:water-off",
    HVAC_MODE_FAN_ONLY: "mdi:fan",
    HVAC_MODE_HEAT: "mdi:white-balance-sunny",
    HVAC_MODE_HEAT_COOL: "mdi:cached",
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Create the IntesisHome climate devices."""
    ihuser = config[CONF_USERNAME]
    ihpass = config[CONF_PASSWORD]
    device_type = config[CONF_DEVICE]

    controller = IntesisHome(
        ihuser,
        ihpass,
        hass.loop,
        websession=async_get_clientsession(hass),
        device_type=device_type,
    )
    await controller.connect()

    if len(controller.get_devices()) > 0:
        async_add_entities(
            [
                IntesisAC(deviceid, device, controller)
                for deviceid, device in controller.get_devices().items()
            ],
            True,
        )
    elif controller.error_message == "WRONG_USERNAME_PASSWORD":
        persistent_notification.create(
            hass, "Wrong username/password.", device_type, "intesishome"
        )
        await controller.stop()
        raise PlatformNotReady()
    else:
        persistent_notification.create(
            hass, controller.error_message, device_type, "intesishome"
        )
        await controller.stop()
        raise PlatformNotReady()


class IntesisAC(ClimateDevice):
    """Represents an Intesishome air conditioning device."""

    def __init__(self, deviceid, ih_device, controller):
        """Initialize the thermostat."""
        _LOGGER.debug("Added climate device with state: %s", repr(ih_device))
        self._controller = controller

        self._deviceid = deviceid
        self._devicename = ih_device.get("name")
        self._devicetype = controller.device_type
        self._has_swing_control = IH_SWING_WIDGET in ih_device.get("widgets")
        self._connected = controller.is_connected
        self._current_temp = None
        self._setpoint_step = ih_device.get("farenheit_type")

        self._max_temp = None
        self._min_temp = None
        self._target_temp = None

        self._run_hours = None
        self._rssi = None
        self._swing = None
        self._swing_list = None
        self._vvane = None
        self._hvane = None
        self._power = False
        self._fan_speed = STATE_UNKNOWN
        self._hvac_mode = STATE_UNKNOWN
        self._connection_retries = 0

        self._hvac_modes = [
            HVAC_MODE_HEAT_COOL,
            HVAC_MODE_COOL,
            HVAC_MODE_HEAT,
            HVAC_MODE_DRY,
            HVAC_MODE_FAN_ONLY,
            HVAC_MODE_OFF,
        ]
        self._fan_modes = controller.get_fan_speed_list(deviceid)

        self._support = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE

        if self._has_swing_control:
            self._support |= SUPPORT_SWING_MODE
            self._swing_list = [SWING_OFF, SWING_BOTH, SWING_VERTICAL, SWING_HORIZONTAL]

        self._controller.add_update_callback(self.update_callback)

    @property
    def name(self):
        """Return the name of the AC device."""
        return self._devicename

    @property
    def temperature_unit(self):
        """Intesishome API uses celsius on the backend."""
        return TEMP_CELSIUS

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        attrs = {}
        if self._has_swing_control:
            attrs["vertical_vane"] = self._vvane
            attrs["horizontal_vane"] = self._hvane

        if self._controller.is_connected:
            attrs["ha_update_type"] = "push"
        else:
            attrs["ha_update_type"] = "poll"

        return attrs

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._deviceid

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(self._deviceid)},
            "name": self._devicename,
            "manufacturer": self._devicetype,
        }

    @property
    def target_temperature_step(self) -> float:
        """Return whether setpoint should be whole or half degree precision."""
        if self._setpoint_step == 1:
            return 1
        return 0.5

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)

        if hvac_mode:
            await self.async_set_hvac_mode(hvac_mode)

        if temperature:
            _LOGGER.debug("Setting %s to %s degrees", self._devicetype, temperature)
            self._target_temp = temperature
            await self._controller.set_temperature(self._deviceid, temperature)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        _LOGGER.debug("Setting %s to %s mode", self._devicetype, hvac_mode)
        if hvac_mode == HVAC_MODE_OFF:
            await self._controller.set_power_off(self._deviceid)
        else:
            # First check device is turned on
            if not self._controller.is_on(self._deviceid):
                await self._controller.set_power_on(self._deviceid)

            # Set the mode
            if hvac_mode == HVAC_MODE_HEAT:
                await self._controller.set_mode_heat(self._deviceid)
            elif hvac_mode == HVAC_MODE_COOL:
                await self._controller.set_mode_cool(self._deviceid)
            elif hvac_mode == HVAC_MODE_HEAT_COOL:
                await self._controller.set_mode_auto(self._deviceid)
            elif hvac_mode == HVAC_MODE_FAN_ONLY:
                await self._controller.set_mode_fan(self._deviceid)
            elif hvac_mode == HVAC_MODE_DRY:
                await self._controller.set_mode_dry(self._deviceid)

            # Send the temperature again in case changing modes has changed it
            if self._target_temp:
                await self._controller.set_temperature(
                    self._deviceid, self._target_temp
                )

    async def async_set_fan_mode(self, fan_mode):
        """Set fan mode (from quiet, low, medium, high, auto)."""
        await self._controller.set_fan_speed(self._deviceid, fan_mode)

    async def async_set_swing_mode(self, swing_mode):
        """Set the vertical vane."""
        if swing_mode == SWING_OFF:
            await self._controller.set_vertical_vane(self._deviceid, "auto/stop")
            await self._controller.set_horizontal_vane(self._deviceid, "auto/stop")
        elif swing_mode == SWING_BOTH:
            await self._controller.set_vertical_vane(self._deviceid, "swing")
            await self._controller.set_horizontal_vane(self._deviceid, "swing")
        elif swing_mode == SWING_HORIZONTAL:
            await self._controller.set_vertical_vane(self._deviceid, "manual3")
            await self._controller.set_horizontal_vane(self._deviceid, "swing")
        elif swing_mode == SWING_VERTICAL:
            await self._controller.set_vertical_vane(self._deviceid, "swing")
            await self._controller.set_horizontal_vane(self._deviceid, "manual3")

    async def async_update(self):
        """Copy values from controller dictionary to climate device."""
        if self._controller.is_disconnected:
            if self._connected:
                self._connected = False
                _LOGGER.error(
                    "Connection to %s API was lost. Attempting to reconnect...",
                    self._devicetype,
                )
            await self._controller.connect()
            self._connection_retries += 1
        else:
            if not self._connected:
                self._connected = True
                _LOGGER.debug("Restored connection to %s API.", self._devicetype)
            self._connection_retries = 0

        self._current_temp = self._controller.get_temperature(self._deviceid)
        self._fan_speed = self._controller.get_fan_speed(self._deviceid)
        self._power = self._controller.is_on(self._deviceid)
        self._min_temp = self._controller.get_min_setpoint(self._deviceid)
        self._max_temp = self._controller.get_max_setpoint(self._deviceid)
        self._rssi = self._controller.get_rssi(self._deviceid)
        self._run_hours = self._controller.get_run_hours(self._deviceid)
        self._target_temp = self._controller.get_setpoint(self._deviceid)
        mode = self._controller.get_mode(self._deviceid)

        # Operation mode
        self._hvac_mode = MAP_OPERATION_MODE.get(mode, STATE_UNKNOWN)

        # Swing mode
        # Climate module only supports one swing setting.
        if self._has_swing_control:
            self._vvane = self._controller.get_vertical_swing(self._deviceid)
            self._hvane = self._controller.get_horizontal_swing(self._deviceid)

            if self._vvane == "swing" and self._hvane == "swing":
                self._swing = SWING_BOTH
            elif self._vvane == "swing":
                self._swing = SWING_VERTICAL
            elif self._hvane == "swing":
                self._swing = SWING_HORIZONTAL
            else:
                self._swing = SWING_OFF

    async def async_will_remove_from_hass(self):
        """Shutdown the controller when the device is being removed."""
        await self._controller.stop()

    @property
    def icon(self):
        """Return the icon for the current state."""
        icon = None
        if self._power:
            icon = MAP_STATE_ICONS.get(self._hvac_mode)
        return icon

    def update_callback(self):
        """Let HA know there has been an update from the controller."""
        _LOGGER.debug("%s API sent a status update.", self._devicetype)
        self.schedule_update_ha_state(True)

    @property
    def min_temp(self):
        """Return the minimum temperature for the current mode of operation."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature for the current mode of operation."""
        return self._max_temp

    @property
    def should_poll(self):
        """Poll for updates if pyIntesisHome doesn't have a socket open."""
        # This could be switched on controller.is_connected, but HA doesn't
        # seem to handle dynamically changing from push to poll.
        return True

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self._hvac_modes

    @property
    def fan_mode(self):
        """Return whether the fan is on."""
        return self._fan_speed

    @property
    def swing_mode(self):
        """Return current swing mode."""
        return self._swing

    @property
    def fan_modes(self):
        """List of available fan modes."""
        return self._fan_modes

    @property
    def swing_modes(self):
        """List of available swing positions."""
        return self._swing_list

    @property
    def assumed_state(self) -> bool:
        """If the device is not connected we have to assume state."""
        return not self._connected

    @property
    def available(self) -> bool:
        """If the device hasn't been able to connect, mark as unavailable."""
        return self._connected

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temp

    @property
    def hvac_mode(self):
        """Return the current mode of operation if unit is on."""
        if self._power:
            return self._hvac_mode
        return HVAC_MODE_OFF

    @property
    def target_temperature(self):
        """Return the current setpoint temperature if unit is on."""
        return self._target_temp

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support
