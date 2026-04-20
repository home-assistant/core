"""Support for Button entities of the Evohome integration."""

from __future__ import annotations

from datetime import timedelta

import evohomeasync2 as evo

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    REQUEST_REFRESH_DEFAULT_COOLDOWN,
    CoordinatorEntity,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVOHOME_DATA
from .coordinator import EvoDataUpdateCoordinator
from .entity import is_valid_zone, unique_zone_id

REFRESH_COOLDOWN = timedelta(seconds=REQUEST_REFRESH_DEFAULT_COOLDOWN)


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
        EvoRefreshLocationButton(coordinator),
        EvoResetSystemButton(coordinator, tcs),
    ]

    entities.extend(
        [EvoResetZoneButton(coordinator, z) for z in tcs.zones if is_valid_zone(z)]
    )

    if tcs.hotwater:
        entities.append(EvoResetDhwButton(coordinator, tcs.hotwater))

    async_add_entities(entities)


class EvoRefreshLocationButton(
    CoordinatorEntity[EvoDataUpdateCoordinator], ButtonEntity
):
    """Button entity to force a refresh of a Location's status."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: EvoDataUpdateCoordinator) -> None:
        """Initialize the Location refresh button."""
        super().__init__(coordinator, context=coordinator.loc.id)

        self._attr_unique_id = f"{coordinator.loc.id}_refresh"
        self._attr_name = f"Refresh {coordinator.loc.name}"

    async def async_press(self) -> None:
        """Request the coordinator to refresh the Location's status."""

        # The coordinator's debouncer will coalesce rapid calls, but we also warn
        # the user if the last refresh was very recent to make the limit explicit.
        last_refresh = self.coordinator.last_update_success_time
        if (
            last_refresh is not None
            and dt_util.utcnow() - last_refresh < REFRESH_COOLDOWN
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refresh_too_recent",
                translation_placeholders={
                    "seconds": str(REQUEST_REFRESH_DEFAULT_COOLDOWN),
                },
            )

        await self.coordinator.async_request_refresh()


class EvoResetButtonBase(CoordinatorEntity[EvoDataUpdateCoordinator], ButtonEntity):
    """Base for Evohome's Button entities."""

    _attr_entity_category = EntityCategory.CONFIG

    _evo_device: evo.ControlSystem | evo.HotWater | evo.Zone

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.ControlSystem | evo.HotWater | evo.Zone,
    ) -> None:
        """Initialize an Evohome reset button entity."""
        super().__init__(coordinator, context=evo_device.id)
        self._evo_device = evo_device

    async def async_press(self) -> None:
        """Reset the Evohome entity to its base operating mode."""
        await self.coordinator.call_client_api(self._evo_device.reset())


class EvoResetSystemButton(EvoResetButtonBase):
    """Button entity for system reset."""

    _evo_device: evo.ControlSystem

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.ControlSystem,
    ) -> None:
        """Initialize the system reset button."""
        super().__init__(coordinator, evo_device)

        self._attr_unique_id = f"{evo_device.id}_reset"
        self._attr_name = f"Reset {evo_device.location.name}"


class EvoResetDhwButton(EvoResetButtonBase):
    """Button entity for DHW override reset."""

    _evo_device: evo.HotWater

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.HotWater,
    ) -> None:
        """Initialize the DHW reset button."""
        super().__init__(coordinator, evo_device)

        self._attr_unique_id = f"{evo_device.id}_reset"
        self._attr_name = f"Reset {evo_device.name}"


class EvoResetZoneButton(EvoResetButtonBase):
    """Button entity for zone override reset."""

    _evo_device: evo.Zone

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.Zone,
    ) -> None:
        """Initialize the zone reset button."""
        super().__init__(coordinator, evo_device)
        self._attr_unique_id = f"{unique_zone_id(evo_device)}_reset"

    @property
    def name(self) -> str:
        """Return the name, dynamically following any zone rename."""
        return f"Reset {self._evo_device.name}"
