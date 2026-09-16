"""Support for De Dietrich water heater."""

from dataclasses import dataclass
from typing import Any, cast, override

from diematic_modbus import HotWaterMode
from modbus_connection import ModbusError
from propcache.api import cached_property

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import DeDietrichConfigEntry, DeDietrichDataUpdateCoordinator
from .entity import DeDietrichEntity, DeDietrichEntityDescription

PARALLEL_UPDATES = 0

MODE_TO_HA: dict[HotWaterMode, str] = {
    HotWaterMode.AUTO: STATE_ECO,
    HotWaterMode.TEMP: STATE_PERFORMANCE,
    HotWaterMode.PERM: STATE_HIGH_DEMAND,
}
HA_TO_MODE: dict[str, HotWaterMode] = {v: k for k, v in MODE_TO_HA.items()}

OPERATION_LIST: list[str] = list(HA_TO_MODE)


@dataclass(frozen=True, kw_only=True)
class DeDietrichWaterHeaterEntityDescription(
    DeDietrichEntityDescription, WaterHeaterEntityDescription
):
    """Describe a De Dietrich water heater."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DeDietrichConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the De Dietrich water heater from a config entry."""
    coordinator = entry.runtime_data
    if not coordinator.device.hot_water_present:
        return
    async_add_entities([DeDietrichWaterHeater(coordinator)])


class DeDietrichWaterHeater(DeDietrichEntity, WaterHeaterEntity):
    """Water heater for the hot-water bundle on a De Dietrich boiler."""

    _attr_operation_list: list[str] = OPERATION_LIST
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 1.0
    _attr_max_temp = 80.0
    _attr_target_temperature_step = 1.0
    entity_description: DeDietrichWaterHeaterEntityDescription

    def __init__(self, coordinator: DeDietrichDataUpdateCoordinator) -> None:
        """Initialize the water heater."""
        super().__init__(
            coordinator,
            DeDietrichWaterHeaterEntityDescription(
                key="hot_water",
                component="hot_water",
            ),
        )

    @cached_property
    @override
    def current_operation(self) -> str | None:
        """Return the current HA operation mode."""
        mode = self.coordinator.device.hot_water.mode
        if mode is None:
            return None
        return MODE_TO_HA.get(cast(HotWaterMode, mode))

    @cached_property
    @override
    def current_temperature(self) -> float | None:
        """Return the current tank temperature, falling back to the DPSM module reading."""
        hot_water = self.coordinator.device.hot_water
        if (temp := hot_water.temp) is not None:
            return temp
        return getattr(hot_water, "temp_dpsm", None)

    @cached_property
    @override
    def target_temperature(self) -> float | None:
        """Return the day-mode setpoint."""
        return self.coordinator.device.hot_water.day_target

    @cached_property
    @override
    def target_temperature_low(self) -> float | None:
        """Return the night-mode setpoint."""
        return self.coordinator.device.hot_water.night_target

    @override
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set the boiler's hot-water mode to match the requested HA mode."""
        mode = HA_TO_MODE[operation_mode]
        try:
            await self.coordinator.device.set_hot_water_mode(mode)
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_operation_mode_error",
            ) from err
        await self.coordinator.async_request_refresh()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Write the requested setpoint to the boiler's day-mode target."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        try:
            await self.coordinator.device.hot_water.write("day_target", temperature)
        except (ModbusError, ValueError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_temperature_error",
            ) from err
        await self.coordinator.async_request_refresh()
