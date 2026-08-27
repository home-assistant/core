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
from homeassistant.components.modbus import ModbusHub, get_hub
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_SLAVE,
    DEVICE_DEFAULT_NAME,
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

CALL_TYPE_REGISTER_HOLDING = "holding"
CALL_TYPE_REGISTER_INPUT = "input"
CALL_TYPE_WRITE_REGISTER = "write_register"
DEFAULT_HUB = "modbus_hub"

CONF_HUB = "hub"
PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Required(CONF_SLAVE): vol.All(int, vol.Range(min=0, max=32)),
        vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): cv.string,
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
    """Set up the deprecated YAML configuration."""
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
    modbus_slave = config.get(CONF_SLAVE)
    name = config.get(CONF_NAME)
    hub = get_hub(hass, config[CONF_HUB])
    async_add_entities([Flexit(hub, modbus_slave, name)], True)


class Flexit(ClimateEntity):
    """Representation of a Flexit AC unit."""

    _attr_fan_modes = ["Off", "Low", "Medium", "High"]
    _attr_hvac_mode = HVACMode.COOL
    _attr_hvac_modes = [HVACMode.COOL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self, hub: ModbusHub, modbus_slave: int | None, name: str | None
    ) -> None:
        """Initialize the unit."""
        self._hub = hub
        self._attr_name = name
        self._slave = modbus_slave
        self._attr_fan_mode = None
        self._filter_hours: int | None = None
        self._filter_alarm: int | None = None
        self._heat_recovery: int | None = None
        self._heater_enabled: int | None = None
        self._heating: int | None = None
        self._cooling: int | None = None
        self._alarm = False
        self._outdoor_air_temp: float | None = None

    async def async_update(self) -> None:
        """Update unit attributes."""
        self._attr_target_temperature = await self._async_read_temp_from_register(
            CALL_TYPE_REGISTER_HOLDING, 8
        )
        self._attr_current_temperature = await self._async_read_temp_from_register(
            CALL_TYPE_REGISTER_INPUT, 9
        )
        res = await self._async_read_int16_from_register(CALL_TYPE_REGISTER_HOLDING, 17)
        if self.fan_modes and res < len(self.fan_modes):
            self._attr_fan_mode = self.fan_modes[res]
        self._filter_hours = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_INPUT, 8
        )
        # # Mechanical heat recovery, 0-100%
        self._heat_recovery = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_INPUT, 14
        )
        # # Heater active 0-100%
        self._heating = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_INPUT, 15
        )
        # # Cooling active 0-100%
        self._cooling = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_INPUT, 13
        )
        # # Filter alarm 0/1
        self._filter_alarm = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_INPUT, 27
        )
        # # Heater enabled or not. Does not mean it's necessarily heating
        self._heater_enabled = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_INPUT, 28
        )
        self._outdoor_air_temp = await self._async_read_temp_from_register(
            CALL_TYPE_REGISTER_INPUT, 11
        )

        actual_air_speed = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_INPUT, 48
        )

        if self._heating:
            self._attr_hvac_action = HVACAction.HEATING
        elif self._cooling:
            self._attr_hvac_action = HVACAction.COOLING
        elif self._heat_recovery:
            self._attr_hvac_action = HVACAction.IDLE
        elif actual_air_speed:
            self._attr_hvac_action = HVACAction.FAN
        else:
            self._attr_hvac_action = HVACAction.OFF

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return {
            "filter_hours": self._filter_hours,
            "filter_alarm": self._filter_alarm,
            "heat_recovery": self._heat_recovery,
            "heating": self._heating,
            "heater_enabled": self._heater_enabled,
            "cooling": self._cooling,
            "outdoor_air_temp": self._outdoor_air_temp,
        }

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (target_temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            _LOGGER.error("Received invalid temperature")
            return

        if await self._async_write_int16_to_register(8, int(target_temperature * 10)):
            self._attr_target_temperature = target_temperature
        else:
            _LOGGER.error("Modbus error setting target temperature to Flexit")

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if self.fan_modes and await self._async_write_int16_to_register(
            17, self.fan_modes.index(fan_mode)
        ):
            self._attr_fan_mode = fan_mode
        else:
            _LOGGER.error("Modbus error setting fan mode to Flexit")

    async def _async_read_int16_from_register(
        self, register_type: str, register: int
    ) -> int:
        """Read register using the Modbus hub slave."""
        result = await self._hub.async_pb_call(self._slave, register, 1, register_type)
        if result is None:
            _LOGGER.error("Error reading value from Flexit modbus adapter")
            return -1

        return int(result.registers[0])

    async def _async_read_temp_from_register(
        self, register_type: str, register: int
    ) -> float:
        result = float(
            await self._async_read_int16_from_register(register_type, register)
        )
        if not result:
            return -1
        return result / 10.0

    async def _async_write_int16_to_register(self, register: int, value: int) -> bool:
        result = await self._hub.async_pb_call(
            self._slave, register, value, CALL_TYPE_WRITE_REGISTER
        )
        if not result:
            return False
        return True


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
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.config_entry.entry_id
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
