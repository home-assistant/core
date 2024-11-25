"""Support for the PRT Heatmiser thermostats using the V3 protocol."""

from __future__ import annotations

import logging
from typing import Any

from heatmiserv3 import connection, heatmiser
import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PORT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_THERMOSTATS = "tstats"

TSTATS_SCHEMA = vol.Schema(
    vol.All(
        cv.ensure_list,
        [{vol.Required(CONF_ID): cv.positive_int, vol.Required(CONF_NAME): cv.string}],
    )
)

PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.string,
        vol.Optional(CONF_THERMOSTATS, default=[]): TSTATS_SCHEMA,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the heatmiser thermostat."""

    heatmiser_v3_thermostat = heatmiser.HeatmiserThermostat

    host = config[CONF_HOST]
    port = config[CONF_PORT]

    thermostats = config[CONF_THERMOSTATS]

    uh1_hub = connection.HeatmiserUH1(host, port)

    add_entities(
        [
            HeatmiserV3Thermostat(heatmiser_v3_thermostat, thermostat, uh1_hub)
            for thermostat in thermostats
        ],
        True,
    )


class HeatmiserV3Thermostat(ClimateEntity):
    """Representation of a HeatmiserV3 thermostat."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, therm, device, uh1):
        """Initialize the thermostat."""
        self.therm = therm(device[CONF_ID], "prt", uh1)
        self.uh1 = uh1
        self._name = device[CONF_NAME]
        self._current_temperature = None
        self._target_temperature = None
        self._id = device
        self.dcb = None
        self._attr_hvac_mode = HVACMode.HEAT

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        self._target_temperature = int(temperature)
        self.therm.set_target_temp(self._target_temperature)

    def update(self) -> None:
        """Get the latest data."""
        self.uh1.reopen()
        if not self.uh1.status:
            _LOGGER.error("Failed to update device %s", self._name)
            return
        self.dcb = self.therm.read_dcb()
        self._attr_temperature_unit = (
            UnitOfTemperature.CELSIUS
            if (self.therm.get_temperature_format() == "C")
            else UnitOfTemperature.FAHRENHEIT
        )
        self._current_temperature = int(self.therm.get_floor_temp())
        self._target_temperature = int(self.therm.get_target_temp())
        self._attr_hvac_mode = (
            HVACMode.OFF
            if (int(self.therm.get_current_state()) == 0)
            else HVACMode.HEAT
        )
