"""Support for IntesisHome and airconwithme Smart AC Controllers."""
from __future__ import annotations

import logging
from random import randrange
from typing import Any, NamedTuple

from pyintesishome import IHAuthenticationError, IHConnectionError, IntesisHome
import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PLATFORM_SCHEMA,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_DEVICE,
    CONF_PASSWORD,
    CONF_USERNAME,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

IH_DEVICE_INTESISHOME = "IntesisHome"
IH_DEVICE_AIRCONWITHME = "airconwithme"
IH_DEVICE_ANYWAIR = "anywair"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DEVICE, default=IH_DEVICE_INTESISHOME): vol.In(
            [IH_DEVICE_AIRCONWITHME, IH_DEVICE_ANYWAIR, IH_DEVICE_INTESISHOME]
        ),
    }
)


class SwingSettings(NamedTuple):
    """Settings for swing mode."""

    vvane: str
    hvane: str


MAP_IH_TO_HVAC_MODE = {
    "auto": HVACMode.HEAT_COOL,
    "cool": HVACMode.COOL,
    "dry": HVACMode.DRY,
    "fan": HVACMode.FAN_ONLY,
    "heat": HVACMode.HEAT,
    "off": HVACMode.OFF,
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
    HVACMode.COOL: "mdi:snowflake",
    HVACMode.DRY: "mdi:water-off",
    HVACMode.FAN_ONLY: "mdi:fan",
    HVACMode.HEAT: "mdi:white-balance-sunny",
    HVACMode.HEAT_COOL: "mdi:cached",
}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Create the IntesisHome climate devices."""
    ih_user = config[CONF_USERNAME]
    ih_pass = config[CONF_PASSWORD]
    device_type = config[CONF_DEVICE]

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

    if ih_devices := controller.get_devices():
        async_add_entities(
            [
                IntesisAC(ih_device_id, device, controller)
                for ih_device_id, device in ih_devices.items()
            ],
            True,
        )
    else:
        _LOGGER.error(
            "Error getting device list from %s API: %s",
            device_type,
            controller.error_message,
        )
        await controller.stop()


class IntesisAC(ClimateEntity):
    """Represents an Intesishome air conditioning device."""

    _attr_should_poll = False
    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(self, ih_device_id, ih_device, controller):
        """Initialize the thermostat."""
        self._controller = controller
        self._device_id = ih_device_id
        self._ih_device = ih_device
        self._device_name = ih_device.get("name")
        self._device_type = controller.device_type
        self._connected = None
        self._setpoint_step = 1
        self._current_temp = None
        self._max_temp = None
        self._attr_hvac_modes = []
        self._min_temp = None
        self._target_temp = None
        self._outdoor_temp = None
        self._hvac_mode = None
        self._preset = None
        self._preset_list = [PRESET_ECO, PRESET_COMFORT, PRESET_BOOST]
        self._run_hours = None
        self._rssi = None
        self._swing_list = [SWING_OFF]
        self._vvane = None
        self._hvane = None
        self._power = False
        self._fan_speed = None
        self._attr_supported_features = 0
        self._power_consumption_heat = None
        self._power_consumption_cool = None

        # Setpoint support
        if controller.has_setpoint_control(ih_device_id):
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

        # Setup swing list
        if controller.has_vertical_swing(ih_device_id):
            self._swing_list.append(SWING_VERTICAL)
        if controller.has_horizontal_swing(ih_device_id):
            self._swing_list.append(SWING_HORIZONTAL)
        if SWING_HORIZONTAL in self._swing_list and SWING_VERTICAL in self._swing_list:
            self._swing_list.append(SWING_BOTH)
        if len(self._swing_list) > 1:
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE

        # Setup fan speeds
        self._fan_modes = controller.get_fan_speed_list(ih_device_id)
        if self._fan_modes:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        # Preset support
        if ih_device.get("climate_working_mode"):
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE

        # Setup HVAC modes
        if modes := controller.get_mode_list(ih_device_id):
            mode_list = [MAP_IH_TO_HVAC_MODE[mode] for mode in modes]
            self._attr_hvac_modes.extend(mode_list)
        self._attr_hvac_modes.append(HVACMode.OFF)

    async def async_added_to_hass(self) -> None:
        """Subscribe to event updates."""
        _LOGGER.debug("Added climate device with state: %s", repr(self._ih_device))
        await self._controller.add_update_callback(self.async_update_callback)
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

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if hvac_mode := kwargs.get(ATTR_HVAC_MODE):
            await self.async_set_hvac_mode(hvac_mode)

        if temperature := kwargs.get(ATTR_TEMPERATURE):
            _LOGGER.debug("Setting %s to %s degrees", self._device_type, temperature)
            await self._controller.set_temperature(self._device_id, temperature)
            self._target_temp = temperature

        # Write updated temperature to HA state to avoid flapping (API confirmation is slow)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set operation mode."""
        _LOGGER.debug("Setting %s to %s mode", self._device_type, hvac_mode)
        if hvac_mode == HVACMode.OFF:
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

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode (from quiet, low, medium, high, auto)."""
        await self._controller.set_fan_speed(self._device_id, fan_mode)

        # Updates can take longer than 2 seconds, so update locally
        self._fan_speed = fan_mode
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        ih_preset_mode = MAP_PRESET_MODE_TO_IH.get(preset_mode)
        await self._controller.set_preset_mode(self._device_id, ih_preset_mode)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the vertical vane."""
        if swing_settings := MAP_SWING_TO_IH.get(swing_mode):
            await self._controller.set_vertical_vane(
                self._device_id, swing_settings.vvane
            )
            await self._controller.set_horizontal_vane(
                self._device_id, swing_settings.hvane
            )

    async def async_update(self) -> None:
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

    async def async_will_remove_from_hass(self) -> None:
        """Shutdown the controller when the device is being removed."""
        await self._controller.stop()

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
        if not self._controller.is_connected and self._connected:
            # Connection has dropped
            self._connected = False
            reconnect_minutes = 1 + randrange(10)
            _LOGGER.error(
                "Connection to %s API was lost. Reconnecting in %i minutes",
                self._device_type,
                reconnect_minutes,
            )
            # Schedule reconnection

            async def try_connect(_now):
                await self._controller.connect()

            async_call_later(self.hass, reconnect_minutes * 60, try_connect)

        if self._controller.is_connected and not self._connected:
            # Connection has been restored
            self._connected = True
            _LOGGER.debug("Connection to %s API was restored", self._device_type)

        if not device_id or self._device_id == device_id:
            # Update all devices if no device_id was specified
            _LOGGER.debug(
                "%s API sent a status update for device %s",
                self._device_type,
                device_id,
            )
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
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temp

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current mode of operation if unit is on."""
        if self._power:
            return self._hvac_mode
        return HVACMode.OFF

    @property
    def target_temperature(self):
        """Return the current setpoint temperature if unit is on."""
        return self._target_temp
