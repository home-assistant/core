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
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DEVICE_TYPE_TAGS, DOMAIN, MieleAppliance
from .coordinator import MieleConfigEntry, MieleDataUpdateCoordinator
from .entity import MieleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MieleClimateDescription(ClimateEntityDescription):
    """Class describing Miele climate entities."""

    value_fn: Callable[[MieleDevice], StateType]
    target_fn: Callable[[MieleDevice], StateType]
    zone: int = 0


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
            value_fn=lambda value: cast(int, value.state_temperatures[0].temperature)
            / 100.0,
            target_fn=lambda value: cast(
                int, value.state_target_temperature[0].temperature
            )
            / 100.0,
            zone=0,
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
            value_fn=lambda value: cast(int, value.state_temperatures[1].temperature)
            / 100.0,
            target_fn=lambda value: cast(
                int, value.state_target_temperature[1].temperature
            )
            / 100.0,
            name="Zone 2",
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
            key="thermostat3",
            value_fn=lambda value: cast(int, value.state_temperatures[2].temperature)
            / 100.0,
            target_fn=lambda value: cast(
                int, value.state_target_temperature[2].temperature
            )
            / 100.0,
            name="Zone 3",
            zone=2,
        ),
    ),
)


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
            and (definition.description.value_fn(device) != -32768 / 100.0)
        )
    )


class MieleClimate(MieleEntity, ClimateEntity):
    """Representation of a climate entity."""

    entity_description: MieleClimateDescription

    def __init__(
        self,
        coordinator: MieleDataUpdateCoordinator,
        device_id: str,
        description: MieleClimateDescription,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, device_id, description)
        self.api = coordinator.api
        if (
            self.device.device_type == MieleAppliance.FRIDGE_FREEZER
            and self.entity_description.zone == 0
        ):
            name = DEVICE_TYPE_TAGS[MieleAppliance.FRIDGE]
        elif (
            self.device.device_type == MieleAppliance.FRIDGE_FREEZER
            and self.entity_description.zone == 1
        ):
            name = DEVICE_TYPE_TAGS[MieleAppliance.FREEZER]
        elif (
            self.device.device_type == MieleAppliance.FRIDGE
            and self.entity_description.zone == 0
        ):
            name = DEVICE_TYPE_TAGS[MieleAppliance.FRIDGE]
        elif (
            self.device.device_type == MieleAppliance.FREEZER
            and self.entity_description.zone == 0
        ):
            name = DEVICE_TYPE_TAGS[MieleAppliance.FREEZER]
        elif (
            self.device.device_type == MieleAppliance.WINE_CABINET_FREEZER
            and self.entity_description.zone == 0
        ):
            name = DEVICE_TYPE_TAGS[MieleAppliance.WINE_CABINET]
        elif (
            self.device.device_type == MieleAppliance.WINE_CABINET_FREEZER
            and self.entity_description.zone == 1
        ):
            name = DEVICE_TYPE_TAGS[MieleAppliance.FREEZER]
        else:
            name = cast(str, self.entity_description.name)
        self._attr_translation_key = name

        zone = (
            ""
            if self.entity_description.zone == 0
            else f"{self.entity_description.zone}"
        )
        self._attr_unique_id = f"{device_id}-{description.key}-{zone}"
        self._attr_precision = 1.0
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_target_temperature_step = 1.0
        self._attr_hvac_modes = [HVACMode.COOL]
        self._attr_hvac_mode = HVACMode.COOL
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return cast(float, self.entity_description.value_fn(self.device))

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return cast(float, self.entity_description.target_fn(self.device))

    @property
    def max_temp(self) -> float:
        """Return the maximum target temperature."""
        return cast(
            float,
            self.coordinator.data.actions[self._device_id]
            .target_temperature[self.entity_description.zone]
            .max,
        )

    @property
    def min_temp(self) -> float:
        """Return the minimum target temperature."""
        return cast(
            float,
            self.coordinator.data.actions[self._device_id]
            .target_temperature[self.entity_description.zone]
            .min,
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        try:
            await self.api.set_target_temperature(
                self._device_id, temperature, self.entity_description.zone + 1
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
