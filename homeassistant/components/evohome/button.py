"""Support for Button entities of the Evohome integration."""

from __future__ import annotations

import evohomeasync2 as evo

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import EVOHOME_DATA
from .coordinator import EvoDataUpdateCoordinator
from .entity import EvoEntity, is_valid_zone

BUTTON_DESCRIPTIONS: dict[str, ButtonEntityDescription] = {
    "reset_system": ButtonEntityDescription(
        key="reset_system_mode",
        translation_key="reset_system_mode",
        entity_category=EntityCategory.CONFIG,
    ),
    "reset_dhw": ButtonEntityDescription(
        key="clear_dhw_override",
        translation_key="clear_dhw_override",
        entity_category=EntityCategory.CONFIG,
    ),
    "reset_zone": ButtonEntityDescription(
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

    if tcs.hotwater is not None:
        entities.append(
            EvoResetDhwButton(
                coordinator, tcs.hotwater, BUTTON_DESCRIPTIONS["reset_dhw"]
            )
        )

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

    _attr_has_entity_name = True
    _attr_icon = "mdi:thermostat-box-auto"

    _evo_device: evo.ControlSystem
    _evo_id_attr = "system_id"

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.ControlSystem,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the system reset button."""
        super().__init__(coordinator, evo_device)

        self._attr_translation_placeholders = {"device_name": evo_device.location.name}
        self._attr_unique_id = f"{evo_device.id}_reset"

        self.entity_description = description

    async def async_press(self) -> None:
        """Reset the system.

        The controller will enter auto mode, and the zones will revert to following
        their schedules.
        """
        await self.coordinator.call_client_api(self._evo_device.reset())


class EvoResetDhwButton(EvoEntity, ButtonEntity):
    """Button entity for DHW override reset."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:water-boiler-auto"

    _evo_device: evo.HotWater
    _evo_id_attr = "dhw_id"

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.HotWater,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the DHW reset button."""
        super().__init__(coordinator, evo_device)

        self._attr_translation_placeholders = {"device_name": evo_device.name}
        self._attr_unique_id = f"{evo_device.id}_reset"

        self.entity_description = description

    async def async_press(self) -> None:
        """Clear the DHW override, if any.

        The DHW will revert to following its schedule.
        """
        await self.coordinator.call_client_api(self._evo_device.reset())


class EvoResetZoneButton(EvoEntity, ButtonEntity):
    """Button entity for zone override reset."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:thermostat-auto"

    _evo_device: evo.Zone
    _evo_id_attr = "zone_id"

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.Zone,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the zone reset button."""
        super().__init__(coordinator, evo_device)

        self._attr_translation_placeholders = {"device_name": evo_device.name}

        if evo_device.id == evo_device.tcs.id:
            # this system does not have a distinct ID for the zone
            self._attr_unique_id = f"{evo_device.id}z_reset"
        else:
            self._attr_unique_id = f"{evo_device.id}_reset"

        self.entity_description = description

    async def async_press(self) -> None:
        """Clear the zone override, if any.

        The zone will revert to following its schedule.
        """
        await self.coordinator.call_client_api(self._evo_device.reset())
