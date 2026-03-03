"""Climate platform for the Cosa integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CosaCoordinator
from .types import CosaConfigEntry

PARALLEL_UPDATES = 1

MIN_TEMP = 5
MAX_TEMP = 35


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CosaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cosa climate entities from a config entry."""
    async_add_entities(
        CosaThermostatEntity(coordinator)
        for coordinator in entry.runtime_data.coordinators.values()
    )


class CosaThermostatEntity(CoordinatorEntity[CosaCoordinator], ClimateEntity):
    """Representation of a Cosa smart thermostat."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = 1.0

    def __init__(self, coordinator: CosaCoordinator) -> None:
        """Initialize the thermostat entity."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.endpoint_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.endpoint_id)},
            manufacturer="Cosa",
            model="Smart thermostat",
            name=coordinator.data.get("name", "Cosa Thermostat"),
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.data.get("currentTemperature")

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        data = self.coordinator.data
        mode = data.get("mode")
        option = data.get("option")
        if mode == "manual" and option == "custom":
            return data.get("customTemperature")
        if mode == "manual" and option == "frozen":
            return None
        # In schedule mode, return the active schedule temperature if available
        return data.get("activeTemperature", data.get("homeTemperature"))

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        data = self.coordinator.data
        mode = data.get("mode")
        option = data.get("option")
        if mode == "manual" and option == "frozen":
            return HVACMode.OFF
        if mode == "manual" and option == "custom":
            return HVACMode.HEAT
        if mode == "schedule":
            return HVACMode.AUTO
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        data = self.coordinator.data
        heating = data.get("heating")
        if heating is not None:
            return HVACAction.HEATING if heating else HVACAction.IDLE
        # Infer from current vs target temperature
        current = self.current_temperature
        target = self.target_temperature
        if current is not None and target is not None and current < target:
            return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        api = self.coordinator.api
        endpoint_id = self.coordinator.endpoint_id
        match hvac_mode:
            case HVACMode.OFF:
                success = await api.async_disable(endpoint_id)
            case HVACMode.HEAT:
                success = await api.async_enable_custom_mode(endpoint_id)
            case HVACMode.AUTO:
                success = await api.async_enable_schedule(endpoint_id)
            case _:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="unsupported_hvac_mode",
                )
        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_mode_failed",
            )
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        data = self.coordinator.data
        api = self.coordinator.api
        endpoint_id = self.coordinator.endpoint_id

        success = await api.async_set_target_temperatures(
            endpoint_id,
            home_temp=data.get("homeTemperature", int(temp)),
            away_temp=data.get("awayTemperature", int(temp)),
            sleep_temp=data.get("sleepTemperature", int(temp)),
            custom_temp=int(temp),
        )
        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_temperature_failed",
            )

        # Switch to custom mode if not already
        if data.get("mode") != "manual" or data.get("option") != "custom":
            mode_success = await api.async_enable_custom_mode(endpoint_id)
            if not mode_success:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="set_mode_failed",
                )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn the thermostat on."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn the thermostat off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
