"""Platform for Roth Touchline floor heating controller."""

from __future__ import annotations

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
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import _LOGGER, DOMAIN


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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the configurations from YAML to config flows."""
    # We only import configs from YAML if it hasn't been imported. If there is a config
    # entry marked with SOURCE_IMPORT, it means the YAML config has been imported.
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.source == SOURCE_IMPORT:
            return

    if CONF_HOST in config:
        host = config[CONF_HOST]
        _LOGGER.debug("Roth Touchline host: %s", host)

    if not host:
        _LOGGER.error("No Roth Touchline detected")
        async_create_issue(
            hass,
            DOMAIN,
            "missing_host",
            is_fixable=True,
            severity=IssueSeverity.ERROR,
            translation_key="missing_host",
            translation_placeholders={
                "platform": "climate",
                "integration_title": "Roth Touchline",
            },
        )
        return

    _LOGGER.debug("Attempting to connect to Roth Touchline at %s", host)

    # Verify that the host is reachable
    try:
        py_touchline = PyTouchline(url=host)
        number_of_devices = await hass.async_add_executor_job(
            py_touchline.get_number_of_devices
        )

        if number_of_devices == 0:
            _LOGGER.error("No devices found on Roth Touchline at %s", host)
            async_create_issue(
                hass,
                DOMAIN,
                "no_devices_found",
                is_fixable=False,
                severity=IssueSeverity.ERROR,
                translation_key="no_devices_found",
                translation_placeholders={
                    "platform": "climate",
                    "integration_title": "Roth Touchline",
                },
            )
            return

    except ConnectionError as err:
        _LOGGER.error("Failed to connect to Roth Touchline at %s: %s", host, err)
        async_create_issue(
            hass,
            DOMAIN,
            "connection_failed",
            is_fixable=False,
            severity=IssueSeverity.ERROR,
            translation_key="connection_failed",
            translation_placeholders={
                "platform": "climate",
                "integration_title": "Roth Touchline",
            },
        )
        return

    _LOGGER.debug(
        "Successfully connected to Roth Touchline at %s, importing config", host
    )

    # Log a deprecation warning in the logs
    _LOGGER.warning(
        "YAML configuration for Roth Touchline is deprecated and will be removed "
        "in a future release. Please migrate to the configuration flow in the UI"
    )

    # Create a deprecation issue in the Home Assistant UI
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml_climate",
        breaks_in_ha_version="2025.7.0",  # Adjust to the planned removal version
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "platform": "climate",
            "integration_title": "Roth Touchline",
        },
    )

    # Import YAML as a new config entry
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: host},
        )
    )


# This function sets up the Touchline device from the configuration entry.
async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Touchline device from config entry."""

    # Retrieve stored API and device count from `runtime_data`
    touchline_data = hass.data[DOMAIN].get(config.entry_id)
    if not touchline_data:
        _LOGGER.error("Touchline runtime data missing for entry %s", config.entry_id)
        return

    number_of_devices = touchline_data["device_count"]

    _LOGGER.debug(
        "Setting up %s Touchline devices from stored runtime data", number_of_devices
    )

    # Create entities for each device
    devices = [
        Touchline(PyTouchline(id=device_id, url=touchline_data["host"]))
        for device_id in range(number_of_devices)
    ]

    async_add_entities(devices, True)


# This class represents the Touchline device.
class Touchline(ClimateEntity):
    """Representation of a Touchline device."""

    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, touchline_thermostat):
        """Initialize the Touchline device."""
        self.unit = touchline_thermostat
        self._attr_name = None
        self._device_id = None
        self._controller_id = None
        self._attr_unique_id = None
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._current_operation_mode = None
        self._attr_preset_mode = None
        self._attr_preset_modes = list(PRESET_MODES)

    def update(self) -> None:
        """Update thermostat attributes."""
        self.unit.update()
        self._attr_name = self.unit.get_name()
        self._device_id = self.unit.get_device_id()
        self._controller_id = self.unit.get_controller_id()
        self._attr_unique_id = f"{self._controller_id}_{self._device_id}"
        self._attr_current_temperature = self.unit.get_current_temperature()
        self._attr_target_temperature = self.unit.get_target_temperature()
        self._attr_preset_mode = TOUCHLINE_HA_PRESETS.get(
            (self.unit.get_operation_mode(), self.unit.get_week_program())
        )

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        new_preset_mode = PRESET_MODES[preset_mode]
        self.unit.set_operation_mode(new_preset_mode.mode)
        self.unit.set_week_program(new_preset_mode.program)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        self._current_operation_mode = HVACMode.HEAT

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._attr_target_temperature = kwargs.get(ATTR_TEMPERATURE)
        self.unit.set_target_temperature(self._attr_target_temperature)
