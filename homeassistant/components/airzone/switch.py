"""Support for the Airzone switch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from aioairzone.const import API_ON, AZD_ON, AZD_ZONES

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirzoneConfigEntry
from .coordinator import AirzoneUpdateCoordinator
from .entity import AirzoneEntity, AirzoneZoneEntity


@dataclass(frozen=True, kw_only=True)
class AirzoneSwitchDescription(SwitchEntityDescription):
    """Class to describe an Airzone switch entity."""

    api_param: str


ZONE_SWITCH_TYPES: Final[tuple[AirzoneSwitchDescription, ...]] = (
    AirzoneSwitchDescription(
        api_param=API_ON,
        device_class=SwitchDeviceClass.SWITCH,
        key=AZD_ON,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirzoneConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Airzone switch from a config_entry."""
    coordinator = entry.runtime_data

    added_zones: set[str] = set()

    def _async_entity_listener() -> None:
        """Handle additions of switch."""

        zones_data = coordinator.data.get(AZD_ZONES, {})
        received_zones = set(zones_data)
        new_zones = received_zones - added_zones
        if new_zones:
            async_add_entities(
                AirzoneZoneSwitch(
                    coordinator,
                    description,
                    entry,
                    system_zone_id,
                    zones_data.get(system_zone_id),
                )
                for system_zone_id in new_zones
                for description in ZONE_SWITCH_TYPES
                if description.key in zones_data.get(system_zone_id)
            )
            added_zones.update(new_zones)

    entry.async_on_unload(coordinator.async_add_listener(_async_entity_listener))
    _async_entity_listener()


class AirzoneBaseSwitch(AirzoneEntity, SwitchEntity):
    """Define an Airzone switch."""

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
    """Define an Airzone Zone switch."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: AirzoneSwitchDescription,
        entry: ConfigEntry,
        system_zone_id: str,
        zone_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, system_zone_id, zone_data)

        self._attr_name = None
        self._attr_unique_id = (
            f"{self._attr_unique_id}_{system_zone_id}_{description.key}"
        )
        self.entity_description = description

        self._async_update_attrs()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        param = self.entity_description.api_param
        await self._async_update_hvac_params({param: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        param = self.entity_description.api_param
        await self._async_update_hvac_params({param: False})
