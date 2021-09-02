"""Support for Somfy Thermostat."""
from __future__ import annotations

from pymfy.api.devices.category import Category
from pymfy.api.devices.thermostat import (
    DurationType,
    HvacState,
    RegulationState,
    TargetMode,
    Thermostat,
)

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    PRESET_AWAY,
    PRESET_HOME,
    PRESET_SLEEP,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from .const import COORDINATOR, DOMAIN
from .entity import SomfyEntity

SUPPORTED_CATEGORIES = {Category.HVAC.value}

PRESET_FROST_GUARD = "Frost Guard"
PRESET_GEOFENCING = "Geofencing"
PRESET_MANUAL = "Manual"

PRESETS_MAPPING = {
    TargetMode.AT_HOME: PRESET_HOME,
    TargetMode.AWAY: PRESET_AWAY,
    TargetMode.SLEEP: PRESET_SLEEP,
    TargetMode.MANUAL: PRESET_MANUAL,
    TargetMode.GEOFENCING: PRESET_GEOFENCING,
    TargetMode.FROST_PROTECTION: PRESET_FROST_GUARD,
}
REVERSE_PRESET_MAPPING = {v: k for k, v in PRESETS_MAPPING.items()}

HVAC_MODES_MAPPING = {HvacState.COOL: HVAC_MODE_COOL, HvacState.HEAT: HVAC_MODE_HEAT}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Somfy climate platform."""
    domain_data = hass.data[DOMAIN]
    coordinator = domain_data[COORDINATOR]

    climates = [
        SomfyClimate(coordinator, device_id)
        for device_id, device in coordinator.data.items()
        if SUPPORTED_CATEGORIES & set(device.categories)
    ]

    async_add_entities(climates)


class SomfyClimate(SomfyEntity, ClimateEntity):
    """Representation of a Somfy thermostat device."""

    def __init__(self, coordinator, device_id):
        """Initialize the Somfy device."""
        super().__init__(coordinator, device_id)
        self._climate = None
        self._create_device()

    def _create_device(self):
        """Update the device with the latest data."""
        self._climate = Thermostat(self.device, self.coordinator.client)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._climate.get_ambient_temperature()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._climate.get_target_temperature()

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self._climate.set_target(TargetMode.MANUAL, temperature, DurationType.NEXT_MODE)

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 26.0

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 15.0

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._climate.get_humidity()

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        if self._climate.get_regulation_state() == RegulationState.TIMETABLE:
            return HVAC_MODE_AUTO
        return HVAC_MODES_MAPPING.get(self._climate.get_hvac_state())

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes.

        HEAT and COOL mode are exclusive. End user has to enable a mode manually within the Somfy application.
        So only one mode can be displayed. Auto mode is a scheduler.
        """
        hvac_state = HVAC_MODES_MAPPING[self._climate.get_hvac_state()]
        return [HVAC_MODE_AUTO, hvac_state]

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_AUTO:
            self._climate.cancel_target()
        else:
            self._climate.set_target(
                TargetMode.MANUAL, self.target_temperature, DurationType.FURTHER_NOTICE
            )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        mode = self._climate.get_target_mode()
        return PRESETS_MAPPING.get(mode)

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes."""
        return list(PRESETS_MAPPING.values())

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self.preset_mode == preset_mode:
            return

        if preset_mode == PRESET_HOME:
            temperature = self._climate.get_at_home_temperature()
        elif preset_mode == PRESET_AWAY:
            temperature = self._climate.get_away_temperature()
        elif preset_mode == PRESET_SLEEP:
            temperature = self._climate.get_night_temperature()
        elif preset_mode == PRESET_FROST_GUARD:
            temperature = self._climate.get_frost_protection_temperature()
        elif preset_mode in (PRESET_MANUAL, PRESET_GEOFENCING):
            temperature = self.target_temperature
        else:
            raise ValueError(f"Preset mode not supported: {preset_mode}")

        self._climate.set_target(
            REVERSE_PRESET_MAPPING[preset_mode], temperature, DurationType.NEXT_MODE
        )
