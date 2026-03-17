"""Platform for Roth Touchline floor heating controller."""

from __future__ import annotations

import logging
from typing import Any, NamedTuple

from pytouchline_extended import PyTouchline
import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, CONF_HOST, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PresetMode(NamedTuple):
    """Settings for preset mode."""

    mode: int
    program: int


PRESET_MODES = {
    "Normal": PresetMode(mode=0, program=0),
    "Night": PresetMode(mode=1, program=0),
    "Holiday": PresetMode(mode=2, program=0),
    "Pro 1": PresetMode(mode=0, program=1),
    "Pro 2": PresetMode(mode=0, program=2),
    "Pro 3": PresetMode(mode=0, program=3),
}

TOUCHLINE_HA_PRESETS = {
    (settings.mode, settings.program): preset
    for preset, settings in PRESET_MODES.items()
}

PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend({vol.Required(CONF_HOST): cv.string})


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Touchline devices from a config entry."""
    host = entry.data[CONF_HOST]
    py_touchline = PyTouchline(url=host)
    number_of_devices = int(
        await hass.async_add_executor_job(py_touchline.get_number_of_devices)
    )
    devices = [
        Touchline(PyTouchline(id=device_id, url=host))
        for device_id in range(number_of_devices)
    ]
    async_add_entities(devices, True)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Touchline devices from YAML.

    Touchline now uses config entries. If an entry exists in configuration.yaml,
    the import flow will attempt to import it and create a config entry.
    """
    _LOGGER.warning(
        "Loading touchline via platform config is deprecated; The configuration"
        " has been migrated to a config entry and can be safely removed"
    )
    if not hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )


class Touchline(ClimateEntity):
    """Representation of a Touchline device."""

    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_preset_modes = list(PRESET_MODES)
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, touchline_thermostat):
        """Initialize the Touchline device."""
        self.unit = touchline_thermostat
        self._attr_name = None
        self._current_operation_mode = None
        self._attr_preset_mode = None
        self._device_id = None
        self._controller_id = None
        self._attr_unique_id = None

    def update(self) -> None:
        """Update thermostat attributes."""
        self.unit.update()
        self._attr_name = self.unit.get_name()
        self._device_id = self.unit.get_device_id()
        self._controller_id = self.unit.get_controller_id()
        self._attr_unique_id = f"{self._device_id}_{self._controller_id}"
        self._attr_current_temperature = self.unit.get_current_temperature()
        self._attr_target_temperature = self.unit.get_target_temperature()
        self._attr_preset_mode = TOUCHLINE_HA_PRESETS.get(
            (self.unit.get_operation_mode(), self.unit.get_week_program())
        )

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        preset = PRESET_MODES[preset_mode]
        self.unit.set_operation_mode(preset.mode)
        self.unit.set_week_program(preset.program)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        self._current_operation_mode = HVACMode.HEAT

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._attr_target_temperature = kwargs.get(ATTR_TEMPERATURE)
        self.unit.set_target_temperature(self._attr_target_temperature)
