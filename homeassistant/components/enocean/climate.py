from __future__ import annotations

from abc import ABC

from enocean.utils import combine_hex

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    ClimateEntityDescription,
)
from homeassistant.components.enocean.device import EnOceanEntity
from homeassistant.components.enocean.light import CONF_SENDER_ID
from homeassistant.const import CONF_ID, CONF_NAME, TEMP_CELSIUS
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from homeassistant.core import HomeAssistant

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
    sender_id = config.get(CONF_SENDER_ID, [0x0, 0x0, 0x0, 0x0])
    dev_name = config.get(CONF_NAME, "EnOcean Thermostat A5-20-01")
    dev_id = config.get(CONF_ID, [0x0, 0x0, 0x0, 0x0])
    base_id_to_use = sender_id

    add_entities([EnOceanThermostat(base_id_to_use, dev_id, dev_name)])


class EnOceanThermostat(EnOceanEntity, ClimateEntity, ABC):
    """Representation of an EnOcean Thermostat"""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, base_id_to_use, dev_id, dev_name):
        """Initialize the EnOcean Thermostat source."""
        super().__init__(dev_id, dev_name)
        self._base_id_to_use = base_id_to_use
        self._set_point = DEFAULT_SET_POINT
        self._current_temp = 0
        self._off_value = 0
        self._current_valve_value = 0
        self._attr_unique_id = f"{combine_hex(dev_id)}"
        self.entity_description = ClimateEntityDescription(
            key="thermostat",
            name=dev_name,
        )

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
    def hvac_modes(self) -> list[HVACMode] | list[str]:
        return [HVACMode.HEAT, HVACMode.OFF]

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
