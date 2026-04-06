"""Support for Button entities of the Evohome integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import evohomeasync2 as evo

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import EVOHOME_DATA
from .coordinator import EvoDataUpdateCoordinator
from .entity import EvoChild, EvoEntity, is_valid_zone


@dataclass(frozen=True, kw_only=True)
class EvoButtonEntityDescription(ButtonEntityDescription):
    """Describes an Evohome button entity."""

    press_fn: Callable[[EvoEntity | EvoChild], Any] | None = None


BUTTON_DESCRIPTIONS: dict[str, EvoButtonEntityDescription] = {
    "reset_system": EvoButtonEntityDescription(
        key="reset_system_mode",
        translation_key="reset_system_mode",
        entity_category=EntityCategory.CONFIG,
    ),
    "reset_zone": EvoButtonEntityDescription(
        key="clear_zone_override",
        translation_key="clear_zone_override",
        entity_category=EntityCategory.CONFIG,
    ),
}  # device_class would be RESET, but that is not in ButtonDeviceClass


async def async_setup_platform(
    hass: HomeAssistant,
    _: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the button platform for Evohome."""

    if discovery_info is None:
        return

    coordinator = hass.data[EVOHOME_DATA].coordinator
    tcs = hass.data[EVOHOME_DATA].tcs

    entities: list[ButtonEntity] = [
        EvoResetSystemButton(coordinator, tcs, BUTTON_DESCRIPTIONS["reset_system"])
    ]

    entities.extend(
        [
            EvoResetZoneButton(coordinator, zone, BUTTON_DESCRIPTIONS["reset_zone"])
            for zone in tcs.zones
            if is_valid_zone(zone)
        ]
    )

    async_add_entities(entities)


class EvoResetSystemButton(EvoEntity, ButtonEntity):
    """Button entity for system reset."""

    _attr_icon = "mdi:thermostat-box-auto"

    _evo_device: evo.ControlSystem
    _evo_id_attr = "system_id"

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.ControlSystem,
        description: EvoButtonEntityDescription,
    ) -> None:
        """Initialize the system reset button."""
        super().__init__(coordinator, evo_device)

        self._attr_name = f"Reset {evo_device.location.name}"
        self._attr_unique_id = f"{evo_device.id}_reset"
        self.entity_description = description

    async def async_press(self) -> None:
        """Reset the system.

        The system will enter auto mode, and the zones will revert to following their
        schedules.
        """
        await self.coordinator.call_client_api(self._evo_device.reset())


class EvoResetZoneButton(EvoEntity, ButtonEntity):
    """Button entity for zone override reset."""

    _attr_icon = "mdi:thermostat-auto"

    _evo_device: evo.Zone
    _evo_id_attr = "zone_id"

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.Zone,
        description: EvoButtonEntityDescription,
    ) -> None:
        """Initialize the zone reset button."""
        super().__init__(coordinator, evo_device)

        if evo_device.id == evo_device.tcs.id:
            # this system does not have a distinct ID for the zone
            self._attr_unique_id = f"{evo_device.id}z_reset"
        else:
            self._attr_unique_id = f"{evo_device.id}_reset"

        self.entity_description = description

    @property
    def name(self) -> str | None:
        """Return the name of the evohome entity."""
        return f"Reset {self._evo_device.name}"

    async def async_press(self) -> None:
        """Clear the zone override, if any.

        The zone will revert to following its schedule.
        """
        await self.coordinator.call_client_api(self._evo_device.reset())
