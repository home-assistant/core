"""Support for Homematic thermostats."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_DISCOVER_DEVICES, HM_ATTRIBUTE_SUPPORT
from .entity import HMDevice

HM_TEMP_MAP = ["ACTUAL_TEMPERATURE", "TEMPERATURE"]

HM_HUMI_MAP = ["ACTUAL_HUMIDITY", "HUMIDITY"]

HM_PRESET_MAP = {
    "BOOST_MODE": PRESET_BOOST,
    "COMFORT_MODE": PRESET_COMFORT,
    "LOWERING_MODE": PRESET_ECO,
}

HM_CONTROL_MODE = "CONTROL_MODE"
HMIP_CONTROL_MODE = "SET_POINT_MODE"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Homematic thermostat platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        new_device = HMThermostat(conf)
        devices.append(new_device)

    add_entities(devices, True)


class HMThermostat(HMDevice, ClimateEntity):
    """Representation of a Homematic thermostat."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if self.target_temperature <= self._hmdevice.OFF_VALUE + 0.5:
            return HVACMode.OFF
        if "MANU_MODE" in self._hmdevice.ACTIONNODE:
            if self._hm_control_mode == self._hmdevice.MANU_MODE:
                return HVACMode.HEAT
            return HVACMode.AUTO

        # Simple devices
        if self._data.get("BOOST_MODE"):
            return HVACMode.AUTO
        return HVACMode.HEAT

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        if "AUTO_MODE" in self._hmdevice.ACTIONNODE:
            return [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
        return [HVACMode.HEAT, HVACMode.OFF]

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        if self._data.get("BOOST_MODE", False):
            return "boost"

        if not self._hm_control_mode:
            return PRESET_NONE

        mode = HM_ATTRIBUTE_SUPPORT[HM_CONTROL_MODE][1][self._hm_control_mode]
        mode = mode.lower()

        # Filter HVAC states
        if mode not in (HVACMode.AUTO, HVACMode.HEAT):
            return PRESET_NONE
        return mode

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        preset_modes = []
        for mode in self._hmdevice.ACTIONNODE:
            if mode in HM_PRESET_MAP:
                preset_modes.append(HM_PRESET_MAP[mode])
        return preset_modes

    @property
    def current_humidity(self):
        """Return the current humidity."""
        for node in HM_HUMI_MAP:
            if node in self._data:
                return self._data[node]

    @property
    def current_temperature(self):
        """Return the current temperature."""
        for node in HM_TEMP_MAP:
            if node in self._data:
                return self._data[node]

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._data.get(self._state)

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return None

        self._hmdevice.writeNodeData(self._state, float(temperature))

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.AUTO:
            self._hmdevice.MODE = self._hmdevice.AUTO_MODE
        elif hvac_mode == HVACMode.HEAT:
            self._hmdevice.MODE = self._hmdevice.MANU_MODE
        elif hvac_mode == HVACMode.OFF:
            self._hmdevice.turnoff()

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_BOOST:
            self._hmdevice.MODE = self._hmdevice.BOOST_MODE
        elif preset_mode == PRESET_COMFORT:
            self._hmdevice.MODE = self._hmdevice.COMFORT_MODE
        elif preset_mode == PRESET_ECO:
            self._hmdevice.MODE = self._hmdevice.LOWERING_MODE

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 4.5

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 30.5

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def _hm_control_mode(self):
        """Return Control mode."""
        if HMIP_CONTROL_MODE in self._data:
            return self._data[HMIP_CONTROL_MODE]

        # Homematic
        return self._data.get("CONTROL_MODE")

    def _init_data_struct(self):
        """Generate a data dict (self._data) from the Homematic metadata."""
        self._state = next(iter(self._hmdevice.WRITENODE.keys()))
        self._data[self._state] = None

        if (
            HM_CONTROL_MODE in self._hmdevice.ATTRIBUTENODE
            or HMIP_CONTROL_MODE in self._hmdevice.ATTRIBUTENODE
        ):
            self._data[HM_CONTROL_MODE] = None

        for node in self._hmdevice.SENSORNODE:
            self._data[node] = None
