"""Support for climates."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, TypedDict, cast

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ComelitConfigEntry, ComelitSerialBridge

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


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


class ClimaComelitApiStatus(TypedDict):
    """Comelit Clima API status."""

    hvac_mode: HVACMode
    hvac_action: HVACAction


API_STATUS: dict[str, ClimaComelitApiStatus] = {
    ClimaComelitMode.OFF: ClimaComelitApiStatus(
        hvac_mode=HVACMode.OFF, hvac_action=HVACAction.OFF
    ),
    ClimaComelitMode.LOWER: ClimaComelitApiStatus(
        hvac_mode=HVACMode.COOL, hvac_action=HVACAction.COOLING
    ),
    ClimaComelitMode.UPPER: ClimaComelitApiStatus(
        hvac_mode=HVACMode.HEAT, hvac_action=HVACAction.HEATING
    ),
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
        self._update_attributes()

    def _update_attributes(self) -> None:
        """Update class attributes."""
        device = self.coordinator.data[CLIMATE][self._device.index]
        if not isinstance(device.val, list):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="invalid_clima_data"
            )

        # CLIMATE has a 2 item tuple:
        # - first  for Clima
        # - second for Humidifier
        values = device.val[0]

        _active = values[1]
        _mode = values[2]  # Values from API: "O", "L", "U"
        _automatic = values[3] == ClimaComelitMode.AUTO

        self._attr_current_temperature = values[0] / 10

        self._attr_hvac_action = None
        if _mode == ClimaComelitMode.OFF:
            self._attr_hvac_action = HVACAction.OFF
        if not _active:
            self._attr_hvac_action = HVACAction.IDLE
        if _mode in API_STATUS:
            self._attr_hvac_action = API_STATUS[_mode]["hvac_action"]

        self._attr_hvac_mode = None
        if _mode == ClimaComelitMode.OFF:
            self._attr_hvac_mode = HVACMode.OFF
        if _automatic:
            self._attr_hvac_mode = HVACMode.AUTO
        if _mode in API_STATUS:
            self._attr_hvac_mode = API_STATUS[_mode]["hvac_mode"]

        self._attr_target_temperature = values[4] / 10

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        super()._handle_coordinator_update()

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
        self._attr_target_temperature = target_temp
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""

        if hvac_mode != HVACMode.OFF:
            await self.coordinator.api.set_clima_status(
                self._device.index, ClimaComelitCommand.ON
            )
        await self.coordinator.api.set_clima_status(
            self._device.index, MODE_TO_ACTION[hvac_mode]
        )
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()
