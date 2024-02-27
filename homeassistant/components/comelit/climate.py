"""Support for climates."""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from aiocomelit import ComelitSerialBridgeObject
from aiocomelit.const import CLIMATE

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    UnitOfTemperature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ComelitSerialBridge


class ClimaMode(StrEnum):
    """Serial Bridge clima modes."""

    AUTO = "A"
    OFF = "O"
    LOWER = "L"
    UPPER = "U"


class ClimaAction(StrEnum):
    """Serial Bridge clima actions."""

    OFF = "off"
    ON = "on"
    MANUAL = "man"
    SET = "set"
    AUTO = "auto"


API_STATUS: dict[str, dict[str, Any]] = {
    ClimaMode.OFF: {
        "action": "off",
        "hvac_mode": HVACMode.OFF,
        "hvac_action": HVACAction.OFF,
    },
    ClimaMode.LOWER: {
        "action": "lower",
        "hvac_mode": HVACMode.COOL,
        "hvac_action": HVACAction.COOLING,
    },
    ClimaMode.UPPER: {
        "action": "upper",
        "hvac_mode": HVACMode.HEAT,
        "hvac_action": HVACAction.HEATING,
    },
}

MODE_TO_ACTION: dict[HVACMode, ClimaAction] = {
    HVACMode.OFF: ClimaAction.OFF,
    HVACMode.AUTO: ClimaAction.AUTO,
    HVACMode.COOL: ClimaAction.MANUAL,
    HVACMode.HEAT: ClimaAction.MANUAL,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comelit climates."""

    coordinator: ComelitSerialBridge = hass.data[DOMAIN][config_entry.entry_id]

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
    _enable_turn_on_off_backwards_compatibility = False

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
    def _clima(self) -> list[Any]:
        """Return clima device data."""
        # CLIMATE has a 2 item tuple:
        # - first  for Clima
        # - second for Humidifier
        return self.coordinator.data[CLIMATE][self._device.index].val[0]

    @property
    def _api_mode(self) -> str:
        """Return device mode."""
        # Values from API: "O", "L", "U"
        return self._clima[2]

    @property
    def _api_active(self) -> bool:
        "Return device active/idle."
        return self._clima[1]

    @property
    def _api_automatic(self) -> bool:
        """Return device in automatic/manual mode."""
        return self._clima[3] == ClimaMode.AUTO

    @property
    def target_temperature(self) -> float:
        """Set target temperature."""
        return self._clima[4] / 10

    @property
    def current_temperature(self) -> float:
        """Return current temperature."""
        return self._clima[0] / 10

    @property
    def hvac_mode(self) -> HVACMode | None:
        """HVAC current mode."""

        if self._api_mode == ClimaMode.OFF:
            return HVACMode.OFF

        if self._api_automatic:
            return HVACMode.AUTO

        if self._api_mode in API_STATUS:
            return API_STATUS[self._api_mode]["hvac_mode"]

        return None

    @property
    def hvac_action(self) -> HVACAction | None:
        """HVAC current action."""

        if self._api_mode == ClimaMode.OFF:
            return HVACAction.OFF

        if not self._api_active:
            return HVACAction.IDLE

        if self._api_mode in API_STATUS:
            return API_STATUS[self._api_mode]["hvac_action"]

        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (
            target_temp := kwargs.get(ATTR_TEMPERATURE)
        ) is None or self.hvac_mode == HVACMode.OFF:
            return

        await self.coordinator.api.set_clima_status(
            self._device.index, ClimaAction.MANUAL
        )
        await self.coordinator.api.set_clima_status(
            self._device.index, ClimaAction.SET, target_temp
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""

        if hvac_mode != HVACMode.OFF:
            await self.coordinator.api.set_clima_status(
                self._device.index, ClimaAction.ON
            )
        await self.coordinator.api.set_clima_status(
            self._device.index, MODE_TO_ACTION[hvac_mode]
        )
