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

from .const import _LOGGER, DOMAIN
from .coordinator import ComelitSerialBridge


class ClimaAction(StrEnum):
    """Serial Bridge clima actions."""

    OFF = "off"
    ON = "on"
    MANUAL = "man"
    SET = "set"
    AUTO = "auto"


API_STATUS: dict[str, dict[str, Any]] = {
    "O": {
        "preset": None,
        "action": "off",
        "hvac_mode": HVACMode.OFF,
        "hvac_action": HVACAction.OFF,
    },
    "L": {
        "preset": "ESTATE",
        "action": "lower",
        "hvac_mode": HVACMode.COOL,
        "hvac_action": HVACAction.COOLING,
    },
    "U": {
        "preset": "INVERNO",
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


OFF = "O"


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
    _attr_preset_modes = [
        api["preset"] for api in API_STATUS.values() if api["preset"] is not None
    ]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
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
    def _clima(self) -> list[Any]:
        """Return clima device data."""
        # CLIMATE has 2 turple:
        # - first  for Clima
        # - second for Humidifier
        return self.coordinator.data[CLIMATE][self._device.index].val[0]

    @property
    def _api_preset(self) -> str:
        """Return device preset."""
        # Values from API: "O", "L", "U"
        return self._clima[2]

    @property
    def _api_active(self) -> bool:
        "Return device active/idle."
        return self._clima[1]

    @property
    def _api_automatic(self) -> bool:
        """Return device in automatic/manual mode."""
        return self._clima[3] == "A"

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

        if self._api_preset == OFF:
            return HVACMode.OFF

        if self._api_automatic:
            return HVACMode.AUTO

        if self._api_preset in API_STATUS:
            return API_STATUS[self._api_preset]["hvac_mode"]

        _LOGGER.warning("Unknown preset '%s' in hvac_mode", self._api_preset)
        return None

    @property
    def hvac_action(self) -> HVACAction | None:
        """HVAC current action."""

        if not self._api_active:
            return HVACAction.IDLE

        if self._api_preset in API_STATUS:
            return API_STATUS[self._api_preset]["hvac_action"]

        _LOGGER.warning("Unknown preset '%s' in hvac_action", self._api_preset)
        return None

    @property
    def preset_mode(self) -> str | None:
        """Return preset mode."""

        if self._api_preset in API_STATUS:
            return API_STATUS[self._api_preset]["preset"]

        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (target_temp := kwargs.get(ATTR_TEMPERATURE)) is None:
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

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        for mode in API_STATUS.values():
            if mode["preset"] == preset_mode:
                await self.coordinator.api.set_clima_status(
                    self._device.index,
                    mode["action"],
                    self.target_temperature,
                )
                break
