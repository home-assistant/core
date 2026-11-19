"""Climate on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/zha.climate/
"""

from collections.abc import Mapping
import functools
from typing import Any, override

from zha.application.platforms.climate import ThermostatState
from zha.application.platforms.climate.const import (
    ClimateEntityFeature as ZHAClimateEntityFeature,
    HVACAction as ZHAHVACAction,
    HVACMode as ZHAHVACMode,
)

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_TENTHS, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ZHASupportedFeaturesEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    async_add_entities as zha_async_add_entities,
    convert_zha_error_to_ha_error,
    exclude_none_values,
    get_zha_data,
)
from .weekly_schedule import SIGNAL_WEEKLY_SCHEDULE_UPDATED

ZHA_TO_HA_HVAC_MODE = {
    ZHAHVACMode.OFF: HVACMode.OFF,
    ZHAHVACMode.AUTO: HVACMode.AUTO,
    ZHAHVACMode.HEAT: HVACMode.HEAT,
    ZHAHVACMode.COOL: HVACMode.COOL,
    ZHAHVACMode.HEAT_COOL: HVACMode.HEAT_COOL,
    ZHAHVACMode.DRY: HVACMode.DRY,
    ZHAHVACMode.FAN_ONLY: HVACMode.FAN_ONLY,
}

ZHA_TO_HA_HVAC_ACTION = {
    ZHAHVACAction.OFF: HVACAction.OFF,
    ZHAHVACAction.HEATING: HVACAction.HEATING,
    ZHAHVACAction.COOLING: HVACAction.COOLING,
    ZHAHVACAction.DRYING: HVACAction.DRYING,
    ZHAHVACAction.IDLE: HVACAction.IDLE,
    ZHAHVACAction.FAN: HVACAction.FAN,
    ZHAHVACAction.PREHEATING: HVACAction.PREHEATING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation sensor from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.CLIMATE]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, Thermostat, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class Thermostat(ZHASupportedFeaturesEntity, ClimateEntity):
    """Representation of a ZHA Thermostat device."""

    _attr_precision = PRECISION_TENTHS
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key: str = "thermostat"

    @staticmethod
    @functools.cache
    @override
    def _convert_supported_features(
        zha_features: ZHAClimateEntityFeature,
    ) -> ClimateEntityFeature:
        """Convert ZHA climate features to HA climate features."""
        features = ClimateEntityFeature(0)

        if ZHAClimateEntityFeature.TARGET_TEMPERATURE in zha_features:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if ZHAClimateEntityFeature.TARGET_TEMPERATURE_RANGE in zha_features:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        if ZHAClimateEntityFeature.TARGET_HUMIDITY in zha_features:
            features |= ClimateEntityFeature.TARGET_HUMIDITY
        if ZHAClimateEntityFeature.PRESET_MODE in zha_features:
            features |= ClimateEntityFeature.PRESET_MODE
        if ZHAClimateEntityFeature.FAN_MODE in zha_features:
            features |= ClimateEntityFeature.FAN_MODE
        if ZHAClimateEntityFeature.SWING_MODE in zha_features:
            features |= ClimateEntityFeature.SWING_MODE
        if ZHAClimateEntityFeature.TURN_OFF in zha_features:
            features |= ClimateEntityFeature.TURN_OFF
        if ZHAClimateEntityFeature.TURN_ON in zha_features:
            features |= ClimateEntityFeature.TURN_ON

        return features

    @override
    def _update_capability_attrs(self) -> None:
        """Re-derive capability attributes from the cached state."""
        super()._update_capability_attrs()

        state = self._zha_state
        self._attr_hvac_modes = [ZHA_TO_HA_HVAC_MODE[mode] for mode in state.hvac_modes]
        self._attr_fan_modes = state.fan_modes
        self._attr_preset_modes = state.preset_modes
        self._attr_min_temp = state.min_temp
        self._attr_max_temp = state.max_temp

    @override
    async def async_added_to_hass(self) -> None:
        """Refresh the offered HVAC modes when a weekly schedule link changes."""
        await super().async_added_to_hass()
        self._unsubs.append(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_WEEKLY_SCHEDULE_UPDATED,
                self._async_weekly_schedule_updated,
            )
        )
        provider = getattr(self.entity_data.entity, "weekly_schedule", None)
        if (
            provider is not None
            and (event_name := getattr(provider, "EVENT_VERIFIED_CHANGED", None))
            and (subscribe := getattr(provider, "on_event", None))
        ):
            self._unsubs.append(
                subscribe(event_name, self._async_weekly_schedule_verification_updated)
            )

    @callback
    def _async_weekly_schedule_updated(self) -> None:
        self.async_write_ha_state()

    @callback
    def _async_weekly_schedule_verification_updated(self, verified: bool) -> None:
        if (
            not verified
            and (manager := get_zha_data(self.hass).weekly_schedule_sync) is not None
        ):
            manager.async_schedule_invalidated(self.entity_id)
        self.async_write_ha_state()

    @property
    @override
    def hvac_modes(self) -> list[HVACMode]:
        """Return the HVAC modes.

        Auto runs the thermostat's own weekly schedule, so it is only offered
        after a verified upload or successful linked sync. If the thermostat
        already is in Auto, Auto stays available.
        """
        modes = self._attr_hvac_modes
        if (
            HVACMode.AUTO not in modes
            or self.hvac_mode == HVACMode.AUTO
            or getattr(self.entity_data.entity, "weekly_schedule", None) is None
        ):
            return modes
        manager = get_zha_data(self.hass).weekly_schedule_sync
        if manager is not None and manager.async_schedule_active(self.entity_id):
            return modes
        return [mode for mode in modes if mode != HVACMode.AUTO]

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        state = self._zha_state

        if not isinstance(state, ThermostatState):
            return None

        return exclude_none_values(
            {
                "occupancy": state.occupancy,
                "occupied_cooling_setpoint": state.occupied_cooling_setpoint,
                "occupied_heating_setpoint": state.occupied_heating_setpoint,
                "pi_cooling_demand": state.pi_cooling_demand,
                "pi_heating_demand": state.pi_heating_demand,
                "system_mode": state.sys_mode,
                "unoccupied_cooling_setpoint": state.unoccupied_cooling_setpoint,
                "unoccupied_heating_setpoint": state.unoccupied_heating_setpoint,
            }
        )

    @property
    @override
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._zha_state.current_temperature

    @property
    @override
    def fan_mode(self) -> str | None:
        """Return current FAN mode."""
        return self._zha_state.fan_mode

    @property
    @override
    def preset_mode(self) -> str:
        """Return current preset mode."""
        return self._zha_state.preset_mode

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._zha_state.target_temperature

    @property
    @override
    def native_target_temperature_high(self) -> float | None:
        """Return the upper bound temperature we try to reach."""
        return self._zha_state.target_temperature_high

    @property
    @override
    def native_target_temperature_low(self) -> float | None:
        """Return the lower bound temperature we try to reach."""
        return self._zha_state.target_temperature_low

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return HVAC operation mode."""
        return ZHA_TO_HA_HVAC_MODE.get(self._zha_state.hvac_mode)

    @property
    @override
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        return ZHA_TO_HA_HVAC_ACTION.get(self._zha_state.hvac_action)

    @convert_zha_error_to_ha_error()
    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        await self.entity_data.entity.async_set_fan_mode(fan_mode=fan_mode)
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error()
    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        await self.entity_data.entity.async_set_hvac_mode(hvac_mode=hvac_mode)
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error()
    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.entity_data.entity.async_set_preset_mode(preset_mode=preset_mode)
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error()
    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self.entity_data.entity.async_set_temperature(
            target_temp_low=kwargs.get(ATTR_TARGET_TEMP_LOW),
            target_temp_high=kwargs.get(ATTR_TARGET_TEMP_HIGH),
            temperature=kwargs.get(ATTR_TEMPERATURE),
            hvac_mode=kwargs.get(ATTR_HVAC_MODE),
        )
        self.async_write_ha_state()
