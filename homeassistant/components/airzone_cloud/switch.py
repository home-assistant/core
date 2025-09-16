"""Support for the Airzone Cloud switch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from aioairzone_cloud.const import API_POWER, API_VALUE, AZD_POWER, AZD_ZONES

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AirzoneCloudConfigEntry, AirzoneUpdateCoordinator
from .entity import AirzoneEntity, AirzoneZoneEntity


@dataclass(frozen=True, kw_only=True)
class AirzoneSwitchDescription(SwitchEntityDescription):
    """Class to describe an Airzone switch entity."""

    api_param: str


ZONE_SWITCH_TYPES: Final[tuple[AirzoneSwitchDescription, ...]] = (
    AirzoneSwitchDescription(
        api_param=API_POWER,
        device_class=SwitchDeviceClass.SWITCH,
        key=AZD_POWER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirzoneCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Airzone Cloud switch from a config_entry."""
    coordinator = entry.runtime_data

    # Zones
    async_add_entities(
        AirzoneZoneSwitch(
            coordinator,
            description,
            zone_id,
            zone_data,
        )
        for description in ZONE_SWITCH_TYPES
        for zone_id, zone_data in coordinator.data.get(AZD_ZONES, {}).items()
        if description.key in zone_data
    )


class AirzoneBaseSwitch(AirzoneEntity, SwitchEntity):
    """Define an Airzone Cloud switch."""

    entity_description: AirzoneSwitchDescription

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update switch attributes."""
        self._attr_is_on = self.get_airzone_value(self.entity_description.key)


class AirzoneZoneSwitch(AirzoneZoneEntity, AirzoneBaseSwitch):
    """Define an Airzone Cloud Zone switch."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: AirzoneSwitchDescription,
        zone_id: str,
        zone_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, zone_id, zone_data)

        self._attr_name = None
        self._attr_unique_id = f"{zone_id}_{description.key}"
        self.entity_description = description

        self._async_update_attrs()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        param = self.entity_description.api_param
        params: dict[str, Any] = {
            param: {
                API_VALUE: True,
            }
        }
        await self._async_update_params(params)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        param = self.entity_description.api_param
        params: dict[str, Any] = {
            param: {
                API_VALUE: False,
            }
        }
        await self._async_update_params(params)
