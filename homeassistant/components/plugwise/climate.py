"""Plugwise Climate component for Home Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlugwiseConfigEntry
from .const import DOMAIN, MASTER_THERMOSTATS
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity
from .util import plugwise_command

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlugwiseConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile Thermostats from a config entry."""
    coordinator = entry.runtime_data

    @callback
    def _add_entities() -> None:
        """Add Entities."""
        if not coordinator.new_devices:
            return

        if coordinator.data.gateway["smile_name"] == "Adam":
            async_add_entities(
                PlugwiseClimateEntity(coordinator, device_id)
                for device_id in coordinator.new_devices
                if coordinator.data.devices[device_id]["dev_class"] == "climate"
            )
        else:
            async_add_entities(
                PlugwiseClimateEntity(coordinator, device_id)
                for device_id in coordinator.new_devices
                if coordinator.data.devices[device_id]["dev_class"]
                in MASTER_THERMOSTATS
            )

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


class PlugwiseClimateEntity(PlugwiseEntity, ClimateEntity):
    """Representation of a Plugwise thermostat."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN

    _previous_mode: str = "heating"

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Set up the Plugwise API."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}-climate"

        self._devices = coordinator.data.devices
        self._gateway = coordinator.data.gateway
        gateway_id: str = self._gateway["gateway_id"]
        self._gateway_data = self._devices[gateway_id]

        self._location = device_id
        if (location := self.device.get("location")) is not None:
            self._location = location

        # Determine supported features
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        if self._gateway["cooling_present"] and self._gateway["smile_name"] != "Adam":
            self._attr_supported_features = (
                ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            )
        if HVACMode.OFF in self.hvac_modes:
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )
        if presets := self.device.get("preset_modes"):
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes = presets

        self._attr_min_temp = self.device["thermostat"]["lower_bound"]
        self._attr_max_temp = min(self.device["thermostat"]["upper_bound"], 35.0)
        # Ensure we don't drop below 0.1
        self._attr_target_temperature_step = max(
            self.device["thermostat"]["resolution"], 0.1
        )

    def _previous_action_mode(self, coordinator: PlugwiseDataUpdateCoordinator) -> None:
        """Return the previous action-mode when the regulation-mode is not heating or cooling.

        Helper for set_hvac_mode().
        """
        # When no cooling available, _previous_mode is always heating
        if (
            "regulation_modes" in self._gateway_data
            and "cooling" in self._gateway_data["regulation_modes"]
        ):
            mode = self._gateway_data["select_regulation_mode"]
            if mode in ("cooling", "heating"):
                self._previous_mode = mode

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self.device["sensors"]["temperature"]

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach.

        Connected to the HVACMode combination of AUTO-HEAT.
        """

        return self.device["thermostat"]["setpoint"]

    @property
    def target_temperature_high(self) -> float:
        """Return the temperature we try to reach in case of cooling.

        Connected to the HVACMode combination of AUTO-HEAT_COOL.
        """
        return self.device["thermostat"]["setpoint_high"]

    @property
    def target_temperature_low(self) -> float:
        """Return the heating temperature we try to reach in case of heating.

        Connected to the HVACMode combination AUTO-HEAT_COOL.
        """
        return self.device["thermostat"]["setpoint_low"]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return HVAC operation ie. auto, cool, heat, heat_cool, or off mode."""
        if (
            mode := self.device.get("climate_mode")
        ) is None or mode not in self.hvac_modes:
            return HVACMode.HEAT
        return HVACMode(mode)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return a list of available HVACModes."""
        hvac_modes: list[HVACMode] = []
        if "regulation_modes" in self._gateway_data:
            hvac_modes.append(HVACMode.OFF)

        if "available_schedules" in self.device:
            hvac_modes.append(HVACMode.AUTO)

        if self._gateway["cooling_present"]:
            if "regulation_modes" in self._gateway_data:
                if self._gateway_data["select_regulation_mode"] == "cooling":
                    hvac_modes.append(HVACMode.COOL)
                if self._gateway_data["select_regulation_mode"] == "heating":
                    hvac_modes.append(HVACMode.HEAT)
            else:
                hvac_modes.append(HVACMode.HEAT_COOL)
        else:
            hvac_modes.append(HVACMode.HEAT)

        return hvac_modes

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation if supported."""
        # Keep track of the previous action-mode
        self._previous_action_mode(self.coordinator)
        if (action := self.device.get("control_state")) is not None:
            return HVACAction(action)

        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self.device.get("active_preset")

    @plugwise_command
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        data: dict[str, Any] = {}
        if ATTR_TEMPERATURE in kwargs:
            data["setpoint"] = kwargs.get(ATTR_TEMPERATURE)
        if ATTR_TARGET_TEMP_HIGH in kwargs:
            data["setpoint_high"] = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if ATTR_TARGET_TEMP_LOW in kwargs:
            data["setpoint_low"] = kwargs.get(ATTR_TARGET_TEMP_LOW)

        if mode := kwargs.get(ATTR_HVAC_MODE):
            await self.async_set_hvac_mode(mode)

        await self.coordinator.api.set_temperature(self._location, data)

    @plugwise_command
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the hvac mode."""
        if hvac_mode not in self.hvac_modes:
            hvac_modes = ", ".join(self.hvac_modes)
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_hvac_mode_requested",
                translation_placeholders={
                    "hvac_mode": hvac_mode,
                    "hvac_modes": hvac_modes,
                },
            )

        if hvac_mode == self.hvac_mode:
            return

        if hvac_mode == HVACMode.OFF:
            await self.coordinator.api.set_regulation_mode(hvac_mode)
        else:
            await self.coordinator.api.set_schedule_state(
                self._location,
                "on" if hvac_mode == HVACMode.AUTO else "off",
            )
            if self.hvac_mode == HVACMode.OFF:
                await self.coordinator.api.set_regulation_mode(self._previous_mode)

    @plugwise_command
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        await self.coordinator.api.set_preset(self._location, preset_mode)
