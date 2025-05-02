"""Platform for Miele integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Final, cast

import aiohttp
from pymiele import MieleDevice

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DEVICE_TYPE_TAGS, DISABLED_TEMP_ENTITIES, DOMAIN, MieleAppliance
from .coordinator import MieleConfigEntry, MieleDataUpdateCoordinator
from .entity import MieleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MieleClimateDescription(ClimateEntityDescription):
    """Class describing Miele climate entities."""

    value_fn: Callable[[MieleDevice], StateType]
    target_fn: Callable[[MieleDevice], StateType]
    zone: int = 1


@dataclass
class MieleClimateDefinition:
    """Class for defining climate entities."""

    types: tuple[MieleAppliance, ...]
    description: MieleClimateDescription


CLIMATE_TYPES: Final[tuple[MieleClimateDefinition, ...]] = (
    MieleClimateDefinition(
        types=(
            MieleAppliance.FRIDGE,
            MieleAppliance.FREEZER,
            MieleAppliance.FRIDGE_FREEZER,
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
            MieleAppliance.WINE_CABINET_FREEZER,
        ),
        description=MieleClimateDescription(
            key="thermostat",
            value_fn=(
                lambda value: cast(int, value.state_temperatures[0].temperature) / 100.0
            ),
            target_fn=(
                lambda value: cast(int, value.state_target_temperature[0].temperature)
                / 100.0
            ),
            zone=1,
        ),
    ),
    MieleClimateDefinition(
        types=(
            MieleAppliance.FRIDGE,
            MieleAppliance.FREEZER,
            MieleAppliance.FRIDGE_FREEZER,
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
            MieleAppliance.WINE_CABINET_FREEZER,
        ),
        description=MieleClimateDescription(
            key="thermostat2",
            value_fn=(
                lambda value: cast(int, value.state_temperatures[1].temperature) / 100.0
            ),
            target_fn=(
                lambda value: cast(int, value.state_target_temperature[1].temperature)
                / 100.0
            ),
            translation_key="zone_2",
            zone=2,
        ),
    ),
    MieleClimateDefinition(
        types=(
            MieleAppliance.FRIDGE,
            MieleAppliance.FREEZER,
            MieleAppliance.FRIDGE_FREEZER,
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
            MieleAppliance.WINE_CABINET_FREEZER,
        ),
        description=MieleClimateDescription(
            key="thermostat3",
            value_fn=(
                lambda value: cast(int, value.state_temperatures[2].temperature) / 100.0
            ),
            target_fn=(
                lambda value: cast(int, value.state_target_temperature[2].temperature)
                / 100.0
            ),
            translation_key="zone_3",
            zone=3,
        ),
    ),
)

ZONE1_DEVICES = {
    MieleAppliance.FRIDGE: DEVICE_TYPE_TAGS[MieleAppliance.FRIDGE],
    MieleAppliance.FRIDGE_FREEZER: DEVICE_TYPE_TAGS[MieleAppliance.FRIDGE],
    MieleAppliance.FREEZER: DEVICE_TYPE_TAGS[MieleAppliance.FREEZER],
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MieleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the climate platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        MieleClimate(coordinator, device_id, definition.description)
        for device_id, device in coordinator.data.devices.items()
        for definition in CLIMATE_TYPES
        if (
            device.device_type in definition.types
            and (definition.description.value_fn(device) not in DISABLED_TEMP_ENTITIES)
        )
    )


class MieleClimate(MieleEntity, ClimateEntity):
    """Representation of a climate entity."""

    entity_description: MieleClimateDescription
    _attr_precision = PRECISION_WHOLE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_hvac_modes = [HVACMode.COOL]
    _attr_hvac_mode = HVACMode.COOL
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return cast(float, self.entity_description.value_fn(self.device))

    def __init__(
        self,
        coordinator: MieleDataUpdateCoordinator,
        device_id: str,
        description: MieleClimateDescription,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, device_id, description)

        t_key = self.entity_description.translation_key

        if description.zone == 1:
            t_key = ZONE1_DEVICES.get(
                cast(MieleAppliance, self.device.device_type), "zone_1"
            )
            if self.device.device_type in (
                MieleAppliance.FRIDGE,
                MieleAppliance.FREEZER,
            ):
                self._attr_name = None

        if description.zone == 2:
            if self.device.device_type in (
                MieleAppliance.FRIDGE_FREEZER,
                MieleAppliance.WINE_CABINET_FREEZER,
            ):
                t_key = DEVICE_TYPE_TAGS[MieleAppliance.FREEZER]
            else:
                t_key = "zone_2"
        elif description.zone == 3:
            t_key = "zone_3"

        self._attr_translation_key = t_key
        self._attr_unique_id = f"{device_id}-{description.key}-{description.zone}"

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""

        ret_val = cast(float | None, self.entity_description.target_fn(self.device))
        return ret_val if ret_val is not None else None

    @property
    def max_temp(self) -> float:
        """Return the maximum target temperature."""
        return cast(
            float,
            self.action.target_temperature[self.entity_description.zone - 1].max,
        )

    @property
    def min_temp(self) -> float:
        """Return the minimum target temperature."""
        return cast(
            float,
            self.action.target_temperature[self.entity_description.zone - 1].min,
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        try:
            await self.api.set_target_temperature(
                self._device_id, temperature, self.entity_description.zone
            )
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_state_error",
                translation_placeholders={
                    "entity": self.entity_id,
                },
            ) from err
        await self.coordinator.async_request_refresh()
