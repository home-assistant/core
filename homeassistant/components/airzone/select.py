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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AirzoneUpdateCoordinator
from .entity import AirzoneEntity, AirzoneZoneEntity


@dataclass
class AirzoneSelectDescriptionMixin:
    """Define an entity description mixin for select entities."""

    api_param: str
    options: dict[str, int]


@dataclass
class AirzoneSelectDescription(SelectEntityDescription, AirzoneSelectDescriptionMixin):
    """Class to describe an Airzone select entity."""


GRILLE_ANGLE_OPTIONS: Final[dict[str, int]] = {
    "90º": GrilleAngle.DEG_90,
    "50º": GrilleAngle.DEG_50,
    "45º": GrilleAngle.DEG_45,
    "40º": GrilleAngle.DEG_40,
}

SLEEP_OPTIONS: Final[dict[str, int]] = {
    "Off": SleepTimeout.SLEEP_OFF,
    "30m": SleepTimeout.SLEEP_30,
    "60m": SleepTimeout.SLEEP_60,
    "90m": SleepTimeout.SLEEP_90,
}


ZONE_SELECT_TYPES: Final[tuple[AirzoneSelectDescription, ...]] = (
    AirzoneSelectDescription(
        api_param=API_COLD_ANGLE,
        entity_category=EntityCategory.CONFIG,
        key=AZD_COLD_ANGLE,
        name="Cold Angle",
        options=GRILLE_ANGLE_OPTIONS,
    ),
    AirzoneSelectDescription(
        api_param=API_HEAT_ANGLE,
        entity_category=EntityCategory.CONFIG,
        key=AZD_HEAT_ANGLE,
        name="Heat Angle",
        options=GRILLE_ANGLE_OPTIONS,
    ),
    AirzoneSelectDescription(
        api_param=API_SLEEP,
        entity_category=EntityCategory.CONFIG,
        key=AZD_SLEEP,
        name="Sleep",
        options=SLEEP_OPTIONS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Airzone sensors from a config_entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[AirzoneSelect] = []

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


class AirzoneSelect(AirzoneEntity, SelectEntity):
    """Define an Airzone select."""

    entity_description: AirzoneSelectDescription

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    def _get_option_str(self) -> str | None:
        opt_val = self.get_airzone_value(self.entity_description.key)
        if opt_val is not None:
            for key, val in self.entity_description.options.items():
                if val == opt_val:
                    return key
        return None

    @callback
    def _async_update_attrs(self) -> None:
        """Update select attributes."""
        self._attr_current_option = self._get_option_str()


class AirzoneZoneSelect(AirzoneZoneEntity, AirzoneSelect):
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
        self._attr_options = list(description.options.keys())
        self.entity_description = description

        self._async_update_attrs()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        param = self.entity_description.api_param
        value = self.entity_description.options[option]
        await self._async_update_hvac_params({param: value})
