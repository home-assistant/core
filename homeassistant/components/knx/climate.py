"""Support for KNX/IP climate devices."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Callable

from xknx import XKNX
from xknx.devices import Climate as XknxClimate, ClimateMode as XknxClimateMode
from xknx.dpt.dpt_hvac_mode import HVACControllerMode, HVACOperationMode
from xknx.telegram.address import parse_device_group_address

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, CONF_NAME, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONTROLLER_MODES, DOMAIN, PRESET_MODES
from .knx_entity import KnxEntity
from .schema import ClimateSchema

CONTROLLER_MODES_INV = {value: key for key, value in CONTROLLER_MODES.items()}
PRESET_MODES_INV = {value: key for key, value in PRESET_MODES.items()}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: Callable[[Iterable[Entity]], None],
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up climate(s) for KNX platform."""
    if not discovery_info or not discovery_info["platform_config"]:
        return

    platform_config = discovery_info["platform_config"]
    xknx: XKNX = hass.data[DOMAIN].xknx

    _async_migrate_unique_id(hass, platform_config)
    entities = []
    for entity_config in platform_config:
        entities.append(KNXClimate(xknx, entity_config))

    async_add_entities(entities)


@callback
def _async_migrate_unique_id(
    hass: HomeAssistant, platform_config: list[ConfigType]
) -> None:
    """Change unique_ids used in 2021.4 to include target_temperature GA."""
    entity_registry = er.async_get(hass)
    for entity_config in platform_config:
        # normalize group address strings - ga_temperature_state was the old uid
        ga_temperature_state = parse_device_group_address(
            entity_config[ClimateSchema.CONF_TEMPERATURE_ADDRESS][0]
        )
        old_uid = str(ga_temperature_state)

        entity_id = entity_registry.async_get_entity_id("climate", DOMAIN, old_uid)
        if entity_id is None:
            continue
        ga_target_temperature_state = parse_device_group_address(
            entity_config[ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS][0]
        )
        new_uid = f"{ga_temperature_state}_{ga_target_temperature_state}"
        entity_registry.async_update_entity(entity_id, new_unique_id=new_uid)


class KNXClimate(KnxEntity, ClimateEntity):
    """Representation of a KNX climate device."""

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize of a KNX climate device."""
        self._device: XknxClimate
        super().__init__(self._create_climate(xknx, config))

        self._unique_id = (
            f"{self._device.temperature.group_address_state}_"
            f"{self._device.target_temperature.group_address_state}"
        )
        self._unit_of_measurement = TEMP_CELSIUS

    @staticmethod
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
            setpoint_shift_mode=config[ClimateSchema.CONF_SETPOINT_SHIFT_MODE],
            setpoint_shift_max=config[ClimateSchema.CONF_SETPOINT_SHIFT_MAX],
            setpoint_shift_min=config[ClimateSchema.CONF_SETPOINT_SHIFT_MIN],
            temperature_step=config[ClimateSchema.CONF_TEMPERATURE_STEP],
            group_address_on_off=config.get(ClimateSchema.CONF_ON_OFF_ADDRESS),
            group_address_on_off_state=config.get(
                ClimateSchema.CONF_ON_OFF_STATE_ADDRESS
            ),
            min_temp=config.get(ClimateSchema.CONF_MIN_TEMP),
            max_temp=config.get(ClimateSchema.CONF_MAX_TEMP),
            mode=climate_mode,
            on_off_invert=config[ClimateSchema.CONF_ON_OFF_INVERT],
        )

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    async def async_update(self) -> None:
        """Request a state update from KNX bus."""
        await self._device.sync()
        if self._device.mode is not None:
            await self._device.mode.sync()

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.temperature.value

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return self._device.temperature_step

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

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._device.set_target_temperature(temperature)
        self.async_write_ha_state()

    @property
    def hvac_mode(self) -> str:
        """Return current operation ie. heat, cool, idle."""
        if self._device.supports_on_off and not self._device.is_on:
            return HVAC_MODE_OFF
        if self._device.mode is not None and self._device.mode.supports_controller_mode:
            return CONTROLLER_MODES.get(
                self._device.mode.controller_mode.value, HVAC_MODE_HEAT
            )
        # default to "heat"
        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available operation/controller modes."""
        ha_controller_modes: list[str | None] = []
        if self._device.mode is not None:
            for knx_controller_mode in self._device.mode.controller_modes:
                ha_controller_modes.append(
                    CONTROLLER_MODES.get(knx_controller_mode.value)
                )

        if self._device.supports_on_off:
            if not ha_controller_modes:
                ha_controller_modes.append(HVAC_MODE_HEAT)
            ha_controller_modes.append(HVAC_MODE_OFF)

        hvac_modes = list(set(filter(None, ha_controller_modes)))
        # default to ["heat"]
        return hvac_modes if hvac_modes else [HVAC_MODE_HEAT]

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set operation mode."""
        if self._device.supports_on_off and hvac_mode == HVAC_MODE_OFF:
            await self._device.turn_off()
        else:
            if self._device.supports_on_off and not self._device.is_on:
                await self._device.turn_on()
            if (
                self._device.mode is not None
                and self._device.mode.supports_controller_mode
            ):
                knx_controller_mode = HVACControllerMode(
                    CONTROLLER_MODES_INV.get(hvac_mode)
                )
                await self._device.mode.set_controller_mode(knx_controller_mode)
        self.async_write_ha_state()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp.

        Requires SUPPORT_PRESET_MODE.
        """
        if self._device.mode is not None and self._device.mode.supports_operation_mode:
            return PRESET_MODES.get(self._device.mode.operation_mode.value, PRESET_AWAY)
        return None

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires SUPPORT_PRESET_MODE.
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
