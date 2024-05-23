"""Support for KNX/IP climate devices."""

from __future__ import annotations

from typing import Any

from xknx import XKNX
from xknx.devices import Climate as XknxClimate, ClimateMode as XknxClimateMode
from xknx.dpt.dpt_hvac_mode import HVACControllerMode, HVACOperationMode

from homeassistant import config_entries
from homeassistant.components.climate import (
    PRESET_AWAY,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONTROLLER_MODES,
    CURRENT_HVAC_ACTIONS,
    DATA_KNX_CONFIG,
    DOMAIN,
    PRESET_MODES,
)
from .knx_entity import KnxEntity
from .schema import ClimateSchema

ATTR_COMMAND_VALUE = "command_value"
CONTROLLER_MODES_INV = {value: key for key, value in CONTROLLER_MODES.items()}
PRESET_MODES_INV = {value: key for key, value in PRESET_MODES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate(s) for KNX platform."""
    xknx: XKNX = hass.data[DOMAIN].xknx
    config: list[ConfigType] = hass.data[DATA_KNX_CONFIG][Platform.CLIMATE]

    async_add_entities(KNXClimate(xknx, entity_config) for entity_config in config)


def _create_climate(xknx: XKNX, config: ConfigType) -> XknxClimate:
    """Return a KNX Climate device to be used within XKNX."""
    climate_mode = XknxClimateMode(
        xknx,
        name=f"{config[CONF_NAME]} Mode",
        group_address_operation_mode=config.get(
            ClimateSchema.CONF_OPERATION_MODE_ADDRESS
        ),
        group_address_operation_mode_state=config.get(
            ClimateSchema.CONF_OPERATION_MODE_STATE_ADDRESS
        ),
        group_address_controller_status=config.get(
            ClimateSchema.CONF_CONTROLLER_STATUS_ADDRESS
        ),
        group_address_controller_status_state=config.get(
            ClimateSchema.CONF_CONTROLLER_STATUS_STATE_ADDRESS
        ),
        group_address_controller_mode=config.get(
            ClimateSchema.CONF_CONTROLLER_MODE_ADDRESS
        ),
        group_address_controller_mode_state=config.get(
            ClimateSchema.CONF_CONTROLLER_MODE_STATE_ADDRESS
        ),
        group_address_operation_mode_protection=config.get(
            ClimateSchema.CONF_OPERATION_MODE_FROST_PROTECTION_ADDRESS
        ),
        group_address_operation_mode_night=config.get(
            ClimateSchema.CONF_OPERATION_MODE_NIGHT_ADDRESS
        ),
        group_address_operation_mode_comfort=config.get(
            ClimateSchema.CONF_OPERATION_MODE_COMFORT_ADDRESS
        ),
        group_address_operation_mode_standby=config.get(
            ClimateSchema.CONF_OPERATION_MODE_STANDBY_ADDRESS
        ),
        group_address_heat_cool=config.get(ClimateSchema.CONF_HEAT_COOL_ADDRESS),
        group_address_heat_cool_state=config.get(
            ClimateSchema.CONF_HEAT_COOL_STATE_ADDRESS
        ),
        operation_modes=config.get(ClimateSchema.CONF_OPERATION_MODES),
        controller_modes=config.get(ClimateSchema.CONF_CONTROLLER_MODES),
    )

    return XknxClimate(
        xknx,
        name=config[CONF_NAME],
        group_address_temperature=config[ClimateSchema.CONF_TEMPERATURE_ADDRESS],
        group_address_target_temperature=config.get(
            ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS
        ),
        group_address_target_temperature_state=config[
            ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS
        ],
        group_address_setpoint_shift=config.get(
            ClimateSchema.CONF_SETPOINT_SHIFT_ADDRESS
        ),
        group_address_setpoint_shift_state=config.get(
            ClimateSchema.CONF_SETPOINT_SHIFT_STATE_ADDRESS
        ),
        setpoint_shift_mode=config.get(ClimateSchema.CONF_SETPOINT_SHIFT_MODE),
        setpoint_shift_max=config[ClimateSchema.CONF_SETPOINT_SHIFT_MAX],
        setpoint_shift_min=config[ClimateSchema.CONF_SETPOINT_SHIFT_MIN],
        temperature_step=config[ClimateSchema.CONF_TEMPERATURE_STEP],
        group_address_on_off=config.get(ClimateSchema.CONF_ON_OFF_ADDRESS),
        group_address_on_off_state=config.get(ClimateSchema.CONF_ON_OFF_STATE_ADDRESS),
        on_off_invert=config[ClimateSchema.CONF_ON_OFF_INVERT],
        group_address_active_state=config.get(ClimateSchema.CONF_ACTIVE_STATE_ADDRESS),
        group_address_command_value_state=config.get(
            ClimateSchema.CONF_COMMAND_VALUE_STATE_ADDRESS
        ),
        min_temp=config.get(ClimateSchema.CONF_MIN_TEMP),
        max_temp=config.get(ClimateSchema.CONF_MAX_TEMP),
        mode=climate_mode,
    )


class KNXClimate(KnxEntity, ClimateEntity):
    """Representation of a KNX climate device."""

    _device: XknxClimate
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize of a KNX climate device."""
        super().__init__(_create_climate(xknx, config))
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        if self._device.supports_on_off:
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )
        if (
            self._device.mode is not None
            and len(self._device.mode.controller_modes) >= 2
            and HVACControllerMode.OFF in self._device.mode.controller_modes
        ):
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )

        if self.preset_modes:
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
        self._attr_target_temperature_step = self._device.temperature_step
        self._attr_unique_id = (
            f"{self._device.temperature.group_address_state}_"
            f"{self._device.target_temperature.group_address_state}_"
            f"{self._device.target_temperature.group_address}_"
            f"{self._device._setpoint_shift.group_address}"  # noqa: SLF001
        )
        self.default_hvac_mode: HVACMode = config[
            ClimateSchema.CONF_DEFAULT_CONTROLLER_MODE
        ]
        # non-OFF HVAC mode to be used when turning on the device without on_off address
        self._last_hvac_mode: HVACMode = self.default_hvac_mode

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.temperature.value

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._device.target_temperature.value

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        temp = self._device.target_temperature_min
        return temp if temp is not None else super().min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        temp = self._device.target_temperature_max
        return temp if temp is not None else super().max_temp

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        if self._device.supports_on_off:
            await self._device.turn_on()
            self.async_write_ha_state()
            return

        if self._device.mode is not None and self._device.mode.supports_controller_mode:
            knx_controller_mode = HVACControllerMode(
                CONTROLLER_MODES_INV.get(self._last_hvac_mode)
            )
            await self._device.mode.set_controller_mode(knx_controller_mode)
            self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        if self._device.supports_on_off:
            await self._device.turn_off()
            self.async_write_ha_state()
            return

        if (
            self._device.mode is not None
            and HVACControllerMode.OFF in self._device.mode.controller_modes
        ):
            await self._device.mode.set_controller_mode(HVACControllerMode.OFF)
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            await self._device.set_target_temperature(temperature)
            self.async_write_ha_state()

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation ie. heat, cool, idle."""
        if self._device.supports_on_off and not self._device.is_on:
            return HVACMode.OFF
        if self._device.mode is not None and self._device.mode.supports_controller_mode:
            hvac_mode = CONTROLLER_MODES.get(
                self._device.mode.controller_mode.value, self.default_hvac_mode
            )
            if hvac_mode is not HVACMode.OFF:
                self._last_hvac_mode = hvac_mode
            return hvac_mode
        return self.default_hvac_mode

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available operation/controller modes."""
        ha_controller_modes: list[HVACMode | None] = []
        if self._device.mode is not None:
            ha_controller_modes.extend(
                CONTROLLER_MODES.get(knx_controller_mode.value)
                for knx_controller_mode in self._device.mode.controller_modes
            )

        if self._device.supports_on_off:
            if not ha_controller_modes:
                ha_controller_modes.append(self.default_hvac_mode)
            ha_controller_modes.append(HVACMode.OFF)

        hvac_modes = list(set(filter(None, ha_controller_modes)))
        return hvac_modes if hvac_modes else [self.default_hvac_mode]

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if self._device.supports_on_off and not self._device.is_on:
            return HVACAction.OFF
        if self._device.is_active is False:
            return HVACAction.IDLE
        if (
            self._device.mode is not None and self._device.mode.supports_controller_mode
        ) or self._device.is_active:
            return CURRENT_HVAC_ACTIONS.get(self.hvac_mode, HVACAction.IDLE)
        return None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set controller mode."""
        if self._device.mode is not None and self._device.mode.supports_controller_mode:
            knx_controller_mode = HVACControllerMode(
                CONTROLLER_MODES_INV.get(hvac_mode)
            )
            if knx_controller_mode in self._device.mode.controller_modes:
                await self._device.mode.set_controller_mode(knx_controller_mode)
                self.async_write_ha_state()
                return

        if self._device.supports_on_off:
            if hvac_mode == HVACMode.OFF:
                await self._device.turn_off()
            elif not self._device.is_on:
                # for default hvac mode, otherwise above would have triggered
                await self._device.turn_on()
            self.async_write_ha_state()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        if self._device.mode is not None and self._device.mode.supports_operation_mode:
            return PRESET_MODES.get(self._device.mode.operation_mode.value, PRESET_AWAY)
        return None

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        if self._device.mode is None:
            return None

        presets = [
            PRESET_MODES.get(operation_mode.value)
            for operation_mode in self._device.mode.operation_modes
        ]
        return list(filter(None, presets))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self._device.mode is not None and self._device.mode.supports_operation_mode:
            knx_operation_mode = HVACOperationMode(PRESET_MODES_INV.get(preset_mode))
            await self._device.mode.set_operation_mode(knx_operation_mode)
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return device specific state attributes."""
        attr: dict[str, Any] = {}

        if self._device.command_value.initialized:
            attr[ATTR_COMMAND_VALUE] = self._device.command_value.value
        return attr

    async def async_added_to_hass(self) -> None:
        """Store register state change callback."""
        await super().async_added_to_hass()
        if self._device.mode is not None:
            self._device.mode.register_device_updated_cb(self.after_update_callback)
