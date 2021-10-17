# pylint: disable=duplicate-code
"""Support for IntesisHome and airconwithme Smart AC Controllers."""
from __future__ import annotations

import logging
from random import randrange
from typing import NamedTuple

from pyintesishome import (
    IHAuthenticationError,
    IHConnectionError,
    IntesisBase,
    IntesisBox,
    IntesisHome,
    IntesisHomeLocal,
)
from pyintesishome.const import (
    DEVICE_AIRCONWITHME,
    DEVICE_ANYWAIR,
    DEVICE_INTESISBOX,
    DEVICE_INTESISHOME,
    DEVICE_INTESISHOME_LOCAL,
)
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_DEVICE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    TEMP_CELSIUS,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_DEVICE, default=DEVICE_INTESISHOME): vol.In(
            [
                DEVICE_AIRCONWITHME,
                DEVICE_ANYWAIR,
                DEVICE_INTESISBOX,
                DEVICE_INTESISHOME,
                DEVICE_INTESISHOME_LOCAL,
            ]
        ),
    }
)


class SwingSettings(NamedTuple):
    """Settings for swing mode."""

    vvane: str
    hvane: str


MAP_IH_TO_HVAC_MODE = {
    "auto": HVAC_MODE_HEAT_COOL,
    "cool": HVAC_MODE_COOL,
    "dry": HVAC_MODE_DRY,
    "fan": HVAC_MODE_FAN_ONLY,
    "heat": HVAC_MODE_HEAT,
    "off": HVAC_MODE_OFF,
}
MAP_HVAC_MODE_TO_IH = {v: k for k, v in MAP_IH_TO_HVAC_MODE.items()}

MAP_IH_TO_PRESET_MODE = {
    "eco": PRESET_ECO,
    "comfort": PRESET_COMFORT,
    "powerful": PRESET_BOOST,
}
MAP_PRESET_MODE_TO_IH = {v: k for k, v in MAP_IH_TO_PRESET_MODE.items()}

IH_SWING_STOP = "auto/stop"
IH_SWING_SWING = "swing"
MAP_SWING_TO_IH = {
    SWING_OFF: SwingSettings(vvane=IH_SWING_STOP, hvane=IH_SWING_STOP),
    SWING_BOTH: SwingSettings(vvane=IH_SWING_SWING, hvane=IH_SWING_SWING),
    SWING_HORIZONTAL: SwingSettings(vvane=IH_SWING_STOP, hvane=IH_SWING_SWING),
    SWING_VERTICAL: SwingSettings(vvane=IH_SWING_SWING, hvane=IH_SWING_STOP),
}


MAP_STATE_ICONS = {
    HVAC_MODE_COOL: "mdi:snowflake",
    HVAC_MODE_DRY: "mdi:water-off",
    HVAC_MODE_FAN_ONLY: "mdi:fan",
    HVAC_MODE_HEAT: "mdi:white-balance-sunny",
    HVAC_MODE_HEAT_COOL: "mdi:cached",
}


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Create climate entities from config flow."""
    config = config_entry.data
    if "controller" in hass.data[DOMAIN]:
        controller = hass.data[DOMAIN]["controller"].pop(config_entry.unique_id)
        ih_devices = controller.get_devices()
        if ih_devices:
            async_add_entities(
                [
                    IntesisAC(ih_device_id, device, controller)
                    for ih_device_id, device in ih_devices.items()
                ],
                update_before_add=True,
            )
    else:
        await async_setup_platform(hass, config, async_add_entities)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Create the IntesisHome climate devices."""
    ih_user = config.get(CONF_USERNAME)
    ih_host = config.get(CONF_HOST)
    ih_pass = config.get(CONF_PASSWORD)
    device_type = config.get(CONF_DEVICE)
    websession = async_get_clientsession(hass)

    if device_type == DEVICE_INTESISBOX:
        controller = IntesisBox(config[CONF_HOST], loop=hass.loop)
        await controller.connect()
    elif device_type == DEVICE_INTESISHOME_LOCAL:
        controller = IntesisHomeLocal(
            ih_host, ih_user, ih_pass, loop=hass.loop, websession=websession
        )
    else:
        controller = IntesisHome(
            ih_user,
            ih_pass,
            hass.loop,
            websession=async_get_clientsession(hass),
            device_type=device_type,
        )
    try:
        await controller.poll_status()
    except IHAuthenticationError:
        _LOGGER.error("Invalid username or password")
        return
    except IHConnectionError as ex:
        _LOGGER.error("Error connecting to the %s server", device_type)
        raise PlatformNotReady from ex

    ih_devices = controller.get_devices()
    if ih_devices:
        async_add_entities(
            [
                IntesisAC(ih_device_id, device, controller)
                for ih_device_id, device in ih_devices.items()
            ],
            update_before_add=True,
        )
    else:
        _LOGGER.error(
            "Error getting device list from %s API: %s",
            device_type,
            controller.error_message,
        )
        await controller.stop()


# pylint: disable=too-many-instance-attributes, too-many-arguments, too-many-public-methods
class IntesisAC(ClimateEntity):
    """Represents an Intesishome air conditioning device."""

    def __init__(self, ih_device_id, ih_device, controller):
        """Initialize the thermostat."""
        self._controller: IntesisBase = controller
        self._device_id: str = ih_device_id
        self._ih_device: dict[str, dict[str, object]] = ih_device
        self._device_name: str = ih_device.get("name")
        self._device_type: str = controller.device_type
        self._connected: bool = False
        self._setpoint_step: float = 1.0
        self._current_temp: float = None
        self._max_temp: float = None
        self._hvac_mode_list = []
        self._min_temp: int = None
        self._target_temp: float = None
        self._outdoor_temp: float = None
        self._hvac_mode: str = None
        self._preset: str = None
        self._preset_list: list[str] = [PRESET_ECO, PRESET_COMFORT, PRESET_BOOST]
        self._run_hours: int = None
        self._rssi = None
        self._swing_list: list[str] = [SWING_OFF]
        self._vvane: str = None
        self._hvane: str = None
        self._power: bool = False
        self._fan_speed = None
        self._support: int = 0
        self._power_consumption_heat = None
        self._power_consumption_cool = None

        # Setup swing list
        if controller.has_vertical_swing(ih_device_id):
            self._swing_list.append(SWING_VERTICAL)
        if controller.has_horizontal_swing(ih_device_id):
            self._swing_list.append(SWING_HORIZONTAL)
        if SWING_HORIZONTAL in self._swing_list and SWING_VERTICAL in self._swing_list:
            self._swing_list.append(SWING_BOTH)

        # Setup fan speeds
        self._fan_modes = controller.get_fan_speed_list(ih_device_id)

        # Setup HVAC modes
        modes = controller.get_mode_list(ih_device_id)
        if modes:
            mode_list = [MAP_IH_TO_HVAC_MODE[mode] for mode in modes]
            self._hvac_mode_list.extend(mode_list)
        self._hvac_mode_list.append(HVAC_MODE_OFF)

    async def async_added_to_hass(self):
        """Subscribe to event updates."""
        _LOGGER.debug("Added climate device with state: %s", repr(self._ih_device))
        self._controller.add_update_callback(self.async_update_callback)

        if self._device_type is not DEVICE_INTESISBOX:
            try:
                await self._controller.connect()
            except IHConnectionError as ex:
                _LOGGER.error("Exception connecting to IntesisHome: %s", ex)
                raise PlatformNotReady from ex

    @property
    def name(self):
        """Return the name of the AC device."""
        return self._device_name

    @property
    def temperature_unit(self):
        """Intesishome API uses celsius on the backend."""
        return TEMP_CELSIUS

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        attrs = {}
        if self._outdoor_temp:
            attrs["outdoor_temp"] = self._outdoor_temp
        if self._power_consumption_heat:
            attrs["power_consumption_heat_kw"] = round(
                self._power_consumption_heat / 1000, 1
            )
        if self._power_consumption_cool:
            attrs["power_consumption_cool_kw"] = round(
                self._power_consumption_cool / 1000, 1
            )

        return attrs

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._device_id

    @property
    def target_temperature_step(self) -> float:
        """Return whether setpoint should be whole or half degree precision."""
        return self._setpoint_step

    @property
    def preset_modes(self):
        """Return a list of HVAC preset modes."""
        return self._preset_list

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        return self._preset

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)

        if hvac_mode:
            await self.async_set_hvac_mode(hvac_mode)

        if temperature:
            _LOGGER.debug("Setting %s to %s degrees", self._device_type, temperature)
            await self._controller.set_temperature(self._device_id, temperature)
            self._target_temp = temperature

        # Write updated temperature to HA state to avoid flapping (API confirmation is slow)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        _LOGGER.debug("Setting %s to %s mode", self._device_type, hvac_mode)
        if hvac_mode == HVAC_MODE_OFF:
            self._power = False
            await self._controller.set_power_off(self._device_id)
            # Write changes to HA, API can be slow to push changes
            self.async_write_ha_state()
            return

        # First check device is turned on
        if not self._controller.is_on(self._device_id):
            self._power = True
            await self._controller.set_power_on(self._device_id)

        # Set the mode
        await self._controller.set_mode(self._device_id, MAP_HVAC_MODE_TO_IH[hvac_mode])

        # Send the temperature again in case changing modes has changed it
        if self._target_temp:
            await self._controller.set_temperature(self._device_id, self._target_temp)

        # Updates can take longer than 2 seconds, so update locally
        self._hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode):
        """Set fan mode (from quiet, low, medium, high, auto)."""
        await self._controller.set_fan_speed(self._device_id, fan_mode)

        # Updates can take longer than 2 seconds, so update locally
        self._fan_speed = fan_mode
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode):
        """Set preset mode."""
        ih_preset_mode = MAP_PRESET_MODE_TO_IH.get(preset_mode)
        await self._controller.set_preset_mode(self._device_id, ih_preset_mode)

    async def async_set_swing_mode(self, swing_mode):
        """Set the vertical vane."""
        if swing_settings := MAP_SWING_TO_IH.get(swing_mode):
            await self._controller.set_vertical_vane(
                self._device_id, swing_settings.vvane
            )
            await self._controller.set_horizontal_vane(
                self._device_id, swing_settings.hvane
            )

    async def async_update(self):
        """Copy values from controller dictionary to climate device."""
        # Update values from controller's device dictionary
        self._connected = self._controller.is_connected
        self._current_temp = self._controller.get_temperature(self._device_id)
        self._fan_speed = self._controller.get_fan_speed(self._device_id)
        self._power = self._controller.is_on(self._device_id)
        self._min_temp = self._controller.get_min_setpoint(self._device_id)
        self._max_temp = self._controller.get_max_setpoint(self._device_id)
        self._rssi = self._controller.get_rssi(self._device_id)
        self._run_hours = self._controller.get_run_hours(self._device_id)
        self._target_temp = self._controller.get_setpoint(self._device_id)
        self._outdoor_temp = self._controller.get_outdoor_temperature(self._device_id)

        # Operation mode
        mode = self._controller.get_mode(self._device_id)
        self._hvac_mode = MAP_IH_TO_HVAC_MODE.get(mode)

        # Preset mode
        preset = self._controller.get_preset_mode(self._device_id)
        self._preset = MAP_IH_TO_PRESET_MODE.get(preset)

        # Swing mode
        # Climate module only supports one swing setting.
        self._vvane = self._controller.get_vertical_swing(self._device_id)
        self._hvane = self._controller.get_horizontal_swing(self._device_id)

        # Power usage
        self._power_consumption_heat = self._controller.get_heat_power_consumption(
            self._device_id
        )
        self._power_consumption_cool = self._controller.get_cool_power_consumption(
            self._device_id
        )

        if not self._support:
            if self._fan_modes:
                self._support |= SUPPORT_FAN_MODE
            if self._controller.has_setpoint_control(self._device_id):
                self._support |= SUPPORT_TARGET_TEMPERATURE
            if len(self._swing_list) > 1:
                self._support |= SUPPORT_SWING_MODE
            if self._fan_modes:
                self._support |= SUPPORT_FAN_MODE
            if self._ih_device.get("climate_working_mode"):
                self._support |= SUPPORT_PRESET_MODE

    async def async_will_remove_from_hass(self):
        """Shutdown the controller when the device is being removed."""
        self._controller.remove_update_callback(self.async_update_callback)
        await self._controller.stop()
        self._controller = None

    @property
    def icon(self):
        """Return the icon for the current state."""
        icon = None
        if self._power:
            icon = MAP_STATE_ICONS.get(self._hvac_mode)
        return icon

    async def async_update_callback(self, device_id=None):
        """Let HA know there has been an update from the controller."""
        # Track changes in connection state
        if self._controller and not self._controller.is_connected and self._connected:
            # Connection has dropped
            self._connected = False
            reconnect_seconds = 30
            if self._device_type in [
                DEVICE_INTESISHOME,
                DEVICE_AIRCONWITHME,
                DEVICE_ANYWAIR,
            ]:
                # Add a random delay for cloud connections
                reconnect_seconds = randrange(30, 600)

            _LOGGER.info(
                "Connection to %s API was lost. Reconnecting in %i seconds",
                self._device_type,
                reconnect_seconds,
            )

            # Schedule reconnection
            async def try_connect(_now):
                await self._controller.connect()

            async_call_later(self.hass, reconnect_seconds, try_connect)

        if self._controller.is_connected and not self._connected:
            # Connection has been restored
            self._connected = True
            _LOGGER.debug("Connection to %s API was restored", self._device_type)

        if not device_id or self._device_id == device_id:
            # Update all devices if no device_id was specified
            self.async_schedule_update_ha_state(True)

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
        return False

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self._hvac_mode_list

    @property
    def fan_mode(self):
        """Return whether the fan is on."""
        return self._fan_speed

    @property
    def swing_mode(self):
        """Return current swing mode."""
        if self._vvane == IH_SWING_SWING and self._hvane == IH_SWING_SWING:
            swing = SWING_BOTH
        elif self._vvane == IH_SWING_SWING:
            swing = SWING_VERTICAL
        elif self._hvane == IH_SWING_SWING:
            swing = SWING_HORIZONTAL
        else:
            swing = SWING_OFF
        return swing

    @property
    def fan_modes(self):
        """List of available fan modes."""
        return self._fan_modes

    @property
    def swing_modes(self):
        """List of available swing positions."""
        return self._swing_list

    @property
    def available(self) -> bool:
        """If the device hasn't been able to connect, mark as unavailable."""
        return self._connected or self._connected is None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._current_temp

    @property
    def hvac_mode(self):
        """Return the current mode of operation if unit is on."""
        if self._power:
            return self._hvac_mode
        return HVAC_MODE_OFF

    @property
    def target_temperature(self) -> float | None:
        """Return the current setpoint temperature if unit is on."""
        if self._power and self.hvac_mode not in [HVAC_MODE_FAN_ONLY, HVAC_MODE_OFF]:
            return self._target_temp
        return None

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support
