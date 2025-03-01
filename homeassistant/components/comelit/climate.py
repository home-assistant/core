"""Support for climates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

from aiocomelit import ComelitSerialBridgeObject
from aiocomelit.const import CLIMATE

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    UnitOfTemperature,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ComelitConfigEntry, ComelitSerialBridge


class ClimaComelitMode(StrEnum):
    """Serial Bridge clima modes."""

    AUTO = "A"
    OFF = "O"
    LOWER = "L"
    UPPER = "U"


class ClimaComelitCommand(StrEnum):
    """Serial Bridge clima commands."""

    OFF = "off"
    ON = "on"
    MANUAL = "man"
    SET = "set"
    AUTO = "auto"


@dataclass
class ClimaObject:
    """Clima object properties."""

    current_temperature: float
    mode: str
    active: bool
    automatic: bool
    target_temperature: float


API_STATUS: dict[str, dict[str, Any]] = {
    ClimaComelitMode.OFF: {
        "action": "off",
        "hvac_mode": HVACMode.OFF,
        "hvac_action": HVACAction.OFF,
    },
    ClimaComelitMode.LOWER: {
        "action": "lower",
        "hvac_mode": HVACMode.COOL,
        "hvac_action": HVACAction.COOLING,
    },
    ClimaComelitMode.UPPER: {
        "action": "upper",
        "hvac_mode": HVACMode.HEAT,
        "hvac_action": HVACAction.HEATING,
    },
}

MODE_TO_ACTION: dict[HVACMode, ClimaComelitCommand] = {
    HVACMode.OFF: ClimaComelitCommand.OFF,
    HVACMode.AUTO: ClimaComelitCommand.AUTO,
    HVACMode.COOL: ClimaComelitCommand.MANUAL,
    HVACMode.HEAT: ClimaComelitCommand.MANUAL,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ComelitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Comelit climates."""

    coordinator = cast(ComelitSerialBridge, config_entry.runtime_data)

    async_add_entities(
        ComelitClimateEntity(coordinator, device, config_entry.entry_id)
        for device in coordinator.data[CLIMATE].values()
    )


class ComelitClimateEntity(CoordinatorEntity[ComelitSerialBridge], ClimateEntity):
    """Climate device."""

    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.COOL, HVACMode.HEAT, HVACMode.OFF]
    _attr_max_temp = 30
    _attr_min_temp = 5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = PRECISION_TENTHS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: ComelitSerialBridge,
        device: ComelitSerialBridgeObject,
        config_entry_entry_id: str,
    ) -> None:
        """Init light entity."""
        self._api = coordinator.api
        self._device = device
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-{device.index}"
        self._attr_device_info = coordinator.platform_device_info(device, device.type)

    @property
    def _clima(self) -> ClimaObject:
        """Return clima device data."""
        if not isinstance(self._device.val, list):
            raise HomeAssistantError("Invalid clima data")

        # CLIMATE has a 2 item tuple:
        # - first  for Clima
        # - second for Humidifier
        values = self._device.val[0]

        return ClimaObject(
            current_temperature=values[0] / 10,
            mode=values[2],  # Values from API: "O", "L", "U"
            active=values[1],
            automatic=(values[3] == ClimaComelitMode.AUTO),
            target_temperature=values[4] / 10,
        )

    @property
    def target_temperature(self) -> float:
        """Set target temperature."""
        return self._clima.target_temperature

    @property
    def current_temperature(self) -> float:
        """Return current temperature."""
        return self._clima.current_temperature

    @property
    def hvac_mode(self) -> HVACMode | None:
        """HVAC current mode."""

        if self._clima.mode == ClimaComelitMode.OFF:
            return HVACMode.OFF

        if self._clima.automatic:
            return HVACMode.AUTO

        if self._clima.mode in API_STATUS:
            return cast(HVACMode, API_STATUS[self._clima.mode]["hvac_mode"])

        return None

    @property
    def hvac_action(self) -> HVACAction | None:
        """HVAC current action."""

        if self._clima.mode == ClimaComelitMode.OFF:
            return HVACAction.OFF

        if not self._clima.active:
            return HVACAction.IDLE

        if self._clima.mode in API_STATUS:
            return cast(HVACAction, API_STATUS[self._clima.mode]["hvac_action"])

        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (
            target_temp := kwargs.get(ATTR_TEMPERATURE)
        ) is None or self.hvac_mode == HVACMode.OFF:
            return

        await self.coordinator.api.set_clima_status(
            self._device.index, ClimaComelitCommand.MANUAL
        )
        await self.coordinator.api.set_clima_status(
            self._device.index, ClimaComelitCommand.SET, target_temp
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""

        if hvac_mode != HVACMode.OFF:
            await self.coordinator.api.set_clima_status(
                self._device.index, ClimaComelitCommand.ON
            )
        await self.coordinator.api.set_clima_status(
            self._device.index, MODE_TO_ACTION[hvac_mode]
        )
