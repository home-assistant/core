"""Support for climates."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, TypedDict, cast

from aiocomelit import ComelitSerialBridgeObject
from aiocomelit.const import CLIMATE

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    UnitOfTemperature,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PRESET_MODE_AUTO, PRESET_MODE_AUTO_TARGET_TEMP, PRESET_MODE_MANUAL
from .coordinator import ComelitConfigEntry, ComelitSerialBridge
from .entity import ComelitBridgeBaseEntity
from .utils import bridge_api_call, cleanup_stale_entity, load_api_data

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

    AUTO = "auto"
    MANUAL = "man"
    OFF = "off"
    ON = "on"
    SET = "set"
    SNOW = "lower"
    SUN = "upper"


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

HVACMODE_TO_ACTION: dict[HVACMode, ClimaComelitCommand] = {
    HVACMode.OFF: ClimaComelitCommand.OFF,
    HVACMode.COOL: ClimaComelitCommand.SNOW,
    HVACMode.HEAT: ClimaComelitCommand.SUN,
}

PRESET_MODE_TO_ACTION: dict[str, ClimaComelitCommand] = {
    PRESET_MODE_MANUAL: ClimaComelitCommand.MANUAL,
    PRESET_MODE_AUTO: ClimaComelitCommand.AUTO,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ComelitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Comelit climates."""

    coordinator = cast(ComelitSerialBridge, config_entry.runtime_data)

    entities: list[ClimateEntity] = []
    for device in coordinator.data[CLIMATE].values():
        values = load_api_data(device, CLIMATE_DOMAIN)
        if values[0] == 0 and values[4] == 0:
            # No climate data, device is only a humidifier/dehumidifier

            await cleanup_stale_entity(
                hass, config_entry, f"{config_entry.entry_id}-{device.index}", device
            )

            continue

        entities.append(
            ComelitClimateEntity(coordinator, device, config_entry.entry_id)
        )

    async_add_entities(entities)


class ComelitClimateEntity(ComelitBridgeBaseEntity, ClimateEntity):
    """Climate device."""

    _attr_hvac_modes = [HVACMode.COOL, HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = [PRESET_MODE_AUTO, PRESET_MODE_MANUAL]
    _attr_max_temp = 30
    _attr_min_temp = 5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_target_temperature_step = PRECISION_TENTHS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_name = None
    _attr_translation_key = "thermostat"

    def __init__(
        self,
        coordinator: ComelitSerialBridge,
        device: ComelitSerialBridgeObject,
        config_entry_entry_id: str,
    ) -> None:
        """Init light entity."""
        super().__init__(coordinator, device, config_entry_entry_id)
        self._update_attributes()

    def _update_attributes(self) -> None:
        """Update class attributes."""
        device = self.coordinator.data[CLIMATE][self._device.index]
        values = load_api_data(device, CLIMATE_DOMAIN)

        _active = values[1]
        _mode = values[2]  # Values from API: "O", "L", "U"
        _automatic = values[3] == ClimaComelitMode.AUTO

        self._attr_preset_mode = PRESET_MODE_AUTO if _automatic else PRESET_MODE_MANUAL

        self._attr_current_temperature = values[0] / 10

        self._attr_hvac_action = None
        if not _active:
            self._attr_hvac_action = HVACAction.IDLE
        elif _mode in API_STATUS:
            self._attr_hvac_action = API_STATUS[_mode]["hvac_action"]

        self._attr_hvac_mode = None
        if _mode in API_STATUS:
            self._attr_hvac_mode = API_STATUS[_mode]["hvac_mode"]

        self._attr_target_temperature = values[4] / 10

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        super()._handle_coordinator_update()

    @bridge_api_call
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (
            (target_temp := kwargs.get(ATTR_TEMPERATURE)) is None
            or self.hvac_mode == HVACMode.OFF
            or self._attr_preset_mode == PRESET_MODE_AUTO
        ):
            return

        await self.coordinator.api.set_clima_status(
            self._device.index, ClimaComelitCommand.SET, target_temp
        )
        self._attr_target_temperature = target_temp
        self.async_write_ha_state()

    @bridge_api_call
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""

        if self._attr_hvac_mode == HVACMode.OFF:
            await self.coordinator.api.set_clima_status(
                self._device.index, ClimaComelitCommand.ON
            )
        await self.coordinator.api.set_clima_status(
            self._device.index, HVACMODE_TO_ACTION[hvac_mode]
        )
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""

        if self._attr_hvac_mode == HVACMode.OFF:
            return

        await self.coordinator.api.set_clima_status(
            self._device.index, PRESET_MODE_TO_ACTION[preset_mode]
        )
        self._attr_preset_mode = preset_mode

        if preset_mode == PRESET_MODE_AUTO:
            self._attr_target_temperature = PRESET_MODE_AUTO_TARGET_TEMP

        self.async_write_ha_state()
