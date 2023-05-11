"""Support for the Airzone sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from aioairzone.common import GrilleAngle, SleepTimeout
from aioairzone.const import (
    API_COLD_ANGLE,
    API_HEAT_ANGLE,
    API_SLEEP,
    AZD_COLD_ANGLE,
    AZD_HEAT_ANGLE,
    AZD_NAME,
    AZD_SLEEP,
    AZD_ZONES,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AirzoneUpdateCoordinator
from .entity import AirzoneEntity, AirzoneZoneEntity


@dataclass
class AirzoneSelectDescriptionMixin:
    """Define an entity description mixin for select entities."""

    api_param: str


@dataclass
class AirzoneSelectDescription(SelectEntityDescription, AirzoneSelectDescriptionMixin):
    """Class to describe an Airzone select entity."""


GRILLE_ANGLE_OPTIONS: Final[list[str]] = [str(opt.value) for opt in GrilleAngle]

SLEEP_OPTIONS: Final[list[str]] = [str(opt.value) for opt in SleepTimeout]


ZONE_SELECT_TYPES: Final[tuple[AirzoneSelectDescription, ...]] = (
    AirzoneSelectDescription(
        api_param=API_COLD_ANGLE,
        entity_category=EntityCategory.CONFIG,
        key=AZD_COLD_ANGLE,
        name="Cold Angle",
        options=GRILLE_ANGLE_OPTIONS,
        translation_key="grille_angles",
    ),
    AirzoneSelectDescription(
        api_param=API_HEAT_ANGLE,
        entity_category=EntityCategory.CONFIG,
        key=AZD_HEAT_ANGLE,
        name="Heat Angle",
        options=GRILLE_ANGLE_OPTIONS,
        translation_key="grille_angles",
    ),
    AirzoneSelectDescription(
        api_param=API_SLEEP,
        entity_category=EntityCategory.CONFIG,
        key=AZD_SLEEP,
        name="Sleep",
        options=SLEEP_OPTIONS,
        translation_key="sleep_times",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Airzone sensors from a config_entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[AirzoneBaseSelect] = []

    for system_zone_id, zone_data in coordinator.data[AZD_ZONES].items():
        for description in ZONE_SELECT_TYPES:
            if description.key in zone_data:
                entities.append(
                    AirzoneZoneSelect(
                        coordinator,
                        description,
                        entry,
                        system_zone_id,
                        zone_data,
                    )
                )

    async_add_entities(entities)


class AirzoneBaseSelect(AirzoneEntity, SelectEntity):
    """Define an Airzone select."""

    entity_description: AirzoneSelectDescription

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update select attributes."""
        value = self.get_airzone_value(self.entity_description.key)
        if value is not None:
            value = str(value.value)
        self._attr_current_option = value


class AirzoneZoneSelect(AirzoneZoneEntity, AirzoneBaseSelect):
    """Define an Airzone Zone select."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: AirzoneSelectDescription,
        entry: ConfigEntry,
        system_zone_id: str,
        zone_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, system_zone_id, zone_data)

        self._attr_name = f"{zone_data[AZD_NAME]} {description.name}"
        self._attr_unique_id = (
            f"{self._attr_unique_id}_{system_zone_id}_{description.key}"
        )
        self.entity_description = description

        self._async_update_attrs()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        params = {
            self.entity_description.api_param: int(option),
        }
        await self._async_update_hvac_params(params)
