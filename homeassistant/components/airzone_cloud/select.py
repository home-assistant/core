"""Support for the Airzone Cloud select."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from aioairzone_cloud.common import AirQualityMode
from aioairzone_cloud.const import (
    API_AQ_MODE_CONF,
    API_VALUE,
    AZD_AQ_MODE_CONF,
    AZD_ZONES,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirzoneCloudConfigEntry
from .coordinator import AirzoneUpdateCoordinator
from .entity import AirzoneEntity, AirzoneZoneEntity


@dataclass(frozen=True, kw_only=True)
class AirzoneSelectDescription(SelectEntityDescription):
    """Class to describe an Airzone select entity."""

    api_param: str
    options_dict: dict[str, str]


AIR_QUALITY_MAP: Final[dict[str, str]] = {
    "off": AirQualityMode.OFF,
    "on": AirQualityMode.ON,
    "auto": AirQualityMode.AUTO,
}


ZONE_SELECT_TYPES: Final[tuple[AirzoneSelectDescription, ...]] = (
    AirzoneSelectDescription(
        api_param=API_AQ_MODE_CONF,
        entity_category=EntityCategory.CONFIG,
        key=AZD_AQ_MODE_CONF,
        options=list(AIR_QUALITY_MAP),
        options_dict=AIR_QUALITY_MAP,
        translation_key="air_quality",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirzoneCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Airzone Cloud select from a config_entry."""
    coordinator = entry.runtime_data

    # Zones
    async_add_entities(
        AirzoneZoneSelect(
            coordinator,
            description,
            zone_id,
            zone_data,
        )
        for description in ZONE_SELECT_TYPES
        for zone_id, zone_data in coordinator.data.get(AZD_ZONES, {}).items()
        if description.key in zone_data
    )


class AirzoneBaseSelect(AirzoneEntity, SelectEntity):
    """Define an Airzone Cloud select."""

    entity_description: AirzoneSelectDescription
    values_dict: dict[str, str]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    def _get_current_option(self) -> str | None:
        """Get current selected option."""
        value = self.get_airzone_value(self.entity_description.key)
        return self.values_dict.get(value)

    @callback
    def _async_update_attrs(self) -> None:
        """Update select attributes."""
        self._attr_current_option = self._get_current_option()


class AirzoneZoneSelect(AirzoneZoneEntity, AirzoneBaseSelect):
    """Define an Airzone Cloud Zone select."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: AirzoneSelectDescription,
        zone_id: str,
        zone_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, zone_id, zone_data)

        self._attr_unique_id = f"{zone_id}_{description.key}"
        self.entity_description = description
        self.values_dict = {v: k for k, v in description.options_dict.items()}

        self._async_update_attrs()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        param = self.entity_description.api_param
        value = self.entity_description.options_dict[option]
        params: dict[str, Any] = {}
        params[param] = {
            API_VALUE: value,
        }
        await self._async_update_params(params)
