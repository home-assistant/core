"""Support for Button entities of the Evohome integration."""

from __future__ import annotations

import evohomeasync2 as evo

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import EVOHOME_DATA
from .coordinator import EvoDataUpdateCoordinator
from .entity import EvoEntity, is_valid_zone


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

    entities: list[ButtonEntity] = [EvoResetSystemButton(coordinator, tcs)]

    if tcs.hotwater is not None:
        entities.append(EvoResetDhwButton(coordinator, tcs.hotwater))

    entities.extend(
        [EvoResetZoneButton(coordinator, z) for z in tcs.zones if is_valid_zone(z)]
    )

    async_add_entities(entities)


class EvoResetButtonBase(EvoEntity, ButtonEntity):
    """Button entity for system reset."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.ControlSystem | evo.HotWater | evo.Zone,
    ) -> None:
        """Initialize the system reset button."""
        super().__init__(coordinator, evo_device)

        self._attr_unique_id = f"{evo_device.id}_reset"

    async def async_press(self) -> None:
        """Reset the Evohome entity to its base operating mode."""
        await self.coordinator.call_client_api(self._evo_device.reset())


class EvoResetSystemButton(EvoResetButtonBase):
    """Button entity for system reset."""

    _attr_translation_key = "reset_system_mode"

    _evo_device: evo.ControlSystem
    _evo_id_attr = "system_id"

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.ControlSystem,
    ) -> None:
        """Initialize the system reset button."""
        super().__init__(coordinator, evo_device)

        self._attr_translation_placeholders = {"device_name": evo_device.location.name}


class EvoResetDhwButton(EvoResetButtonBase):
    """Button entity for DHW override reset."""

    _attr_translation_key = "clear_dhw_override"

    _evo_device: evo.HotWater
    _evo_id_attr = "dhw_id"

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.HotWater,
    ) -> None:
        """Initialize the DHW reset button."""
        super().__init__(coordinator, evo_device)

        self._attr_translation_placeholders = {"device_name": evo_device.name}


class EvoResetZoneButton(EvoResetButtonBase):
    """Button entity for zone override reset."""

    _attr_translation_key = "clear_zone_override"

    _evo_device: evo.Zone
    _evo_id_attr = "zone_id"

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.Zone,
    ) -> None:
        """Initialize the zone reset button."""
        super().__init__(coordinator, evo_device)

        self._attr_translation_placeholders = {"device_name": evo_device.name}

        if evo_device.id == evo_device.tcs.id:
            # this system does not have a distinct ID for the zone
            self._attr_unique_id = f"{evo_device.id}z_reset"
        else:
            self._attr_unique_id = f"{evo_device.id}_reset"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()

        # zone names are not fixed
        self._attr_translation_placeholders = {"device_name": self._evo_device.name}
