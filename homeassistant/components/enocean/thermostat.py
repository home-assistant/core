from __future__ import annotations

from abc import ABC

from components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from components.enocean.device import EnOceanEntity
from components.enocean.light import CONF_SENDER_ID
from const import CONF_ID, CONF_NAME, TEMP_CELSIUS
from helpers import ConfigType
from helpers.entity_platform import AddEntitiesCallback
from helpers.typing import DiscoveryInfoType

from core import HomeAssistant

MAX_TARGET_TEMP = 40
MIN_TARGET_TEMP = 0
TEMPERATURE_STEP = 1

BASE_ID_TO_USE = "sender_base_id"
DEFAULT_SET_POINT = 20


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the EnOcean thermostat platform."""
    sender_id = config.get(CONF_SENDER_ID)
    dev_name = config.get(CONF_NAME)
    dev_id = config.get(CONF_ID)
    base_id_to_use = config.get(sender_id)

    add_entities([EnOceanThermostat(base_id_to_use, dev_id, dev_name)])


class EnOceanThermostat(EnOceanEntity, ClimateEntity, ABC):
    """Representation of an EnOcean Thermostat"""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, base_id_to_use, dev_id, dev_name):
        """Initialize the EnOcean Thermostat source."""
        super().__init__(dev_id, dev_name)
        self._base_id_to_use = base_id_to_use
        self._set_point = DEFAULT_SET_POINT
        self._current_temp = None
        self._off_value = None
        self._current_valve_value = None

    @property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def hvac_mode(self):
        if self.target_temperature <= self._off_value:
            return HVACMode.OFF
        if self.target_temperature > self._current_valve_value:
            return HVACMode.HEAT
        return HVACMode.HEAT

    @property
    def current_temperature(self) -> float | None:
        return self._current_temp

    @property
    def target_temperature(self) -> float | None:
        return self._set_point

    @property
    def target_temperature_high(self) -> float | None:
        return MAX_TARGET_TEMP

    @property
    def target_temperature_low(self) -> float | None:
        return MIN_TARGET_TEMP

    @property
    def target_temperature_step(self) -> float | None:
        return TEMPERATURE_STEP

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        pass

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode.
        :type hvac_mode: HVACMode
        """
        if hvac_mode == HVACMode.HEAT:
            self.turn_on()
        if hvac_mode == HVACMode.OFF:
            self.turn_off()

    def turn_off(self):
        pass

    def turn_on(self):
        pass
