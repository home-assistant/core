"""Support for the Flexit climate platform."""

import logging
from typing import Any, override

from flexit_modbus import MAX_TEMPERATURE, MIN_TEMPERATURE, FanMode, SystemActivity
from modbus_connection import ModbusError
import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_SLAVE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import FlexitConfigEntry
from .const import DOMAIN
from .coordinator import FlexitDataCoordinator
from .entity import FlexitEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# Kept only so the legacy YAML syntax still validates; the values are no
# longer consumed (see async_setup_platform below).
CONF_HUB = "hub"
PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HUB): cv.string,
        vol.Optional(CONF_SLAVE): cv.positive_int,
        vol.Optional(CONF_NAME): cv.string,
    }
)

FLEXIT_TO_HA_FAN_MODE = {
    FanMode.OFF: "Off",
    FanMode.LOW: "Low",
    FanMode.MEDIUM: "Medium",
    FanMode.HIGH: "High",
}
HA_TO_FLEXIT_FAN_MODE = {value: key for key, value in FLEXIT_TO_HA_FAN_MODE.items()}

FLEXIT_TO_HA_HVAC_ACTION = {
    SystemActivity.OFF: HVACAction.OFF,
    SystemActivity.FAN: HVACAction.FAN,
    SystemActivity.HEAT_RECOVERY: HVACAction.IDLE,
    SystemActivity.COOLING: HVACAction.COOLING,
    SystemActivity.HEATING: HVACAction.HEATING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlexitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Flexit climate platform."""
    async_add_entities([FlexitClimate(entry.runtime_data)])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Handle deprecated YAML configuration.

    Flexit now uses config entries. The Modbus connection details (host and
    port) live in a separate ``modbus:`` hub configuration that is not
    reachable from here, so the YAML configuration cannot be imported
    automatically; the user has to set the integration up again via the UI.
    """
    ir.async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml_no_import",
        breaks_in_ha_version="2027.3.0",
        is_fixable=False,
        is_persistent=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml_no_import",
        translation_placeholders={"domain": DOMAIN, "integration_title": "Flexit"},
    )


class FlexitClimate(FlexitEntity, ClimateEntity):
    """Representation of a Flexit AC unit."""

    _attr_name = None
    _attr_fan_modes = list(HA_TO_FLEXIT_FAN_MODE)
    _attr_hvac_mode = HVACMode.HEAT_COOL
    _attr_hvac_modes = [HVACMode.HEAT_COOL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = MIN_TEMPERATURE
    _attr_max_temp = MAX_TEMPERATURE

    def __init__(self, coordinator: FlexitDataCoordinator) -> None:
        """Initialize the unit."""
        assert coordinator.config_entry is not None
        super().__init__(coordinator, coordinator.config_entry.entry_id)
        self._set_attr()

    @override
    def _handle_coordinator_update(self) -> None:
        """Handle entity update."""
        self._set_attr()
        super()._handle_coordinator_update()

    def _set_attr(self) -> None:
        device = self.coordinator.device
        measurements = device.measurements

        fan_mode = device.fan_mode
        activity = device.activity

        self._attr_target_temperature = device.target_temperature
        self._attr_current_temperature = measurements.supply_air_temperature
        self._attr_fan_mode = (
            FLEXIT_TO_HA_FAN_MODE.get(fan_mode) if fan_mode is not None else None
        )
        self._attr_hvac_action = (
            FLEXIT_TO_HA_HVAC_ACTION.get(activity) if activity is not None else None
        )
        self._attr_extra_state_attributes = {
            "filter_hours": measurements.filter_running_hours,
            "filter_alarm": measurements.filter_alarm,
            "heat_recovery": measurements.heat_exchanger_regulation,
            "heating": measurements.electric_heater_regulation,
            "heater_enabled": measurements.electric_heater_enabled,
            "cooling": measurements.cooling_regulation,
            "outdoor_air_temp": measurements.outdoor_air_temperature,
        }

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temperature = kwargs[ATTR_TEMPERATURE]
        try:
            await self.coordinator.device.async_set_target_temperature(
                target_temperature
            )
        except ModbusError as err:
            raise HomeAssistantError("Failed to set target temperature") from err
        await self.coordinator.async_request_refresh()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        try:
            await self.coordinator.device.async_set_fan_mode(
                HA_TO_FLEXIT_FAN_MODE[fan_mode]
            )
        except ModbusError as err:
            raise HomeAssistantError("Failed to set fan mode") from err
        await self.coordinator.async_request_refresh()
