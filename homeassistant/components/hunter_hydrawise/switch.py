"""Support for Hydrawise cloud switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_SUSPEND_DAYS,
    DOMAIN,
    LOGGER,
)
from .coordinator import HydrawiseDataUpdateCoordinator, HydrawiseEntity
from .hydrawiser import Hydrawiser

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="suspend_zone",
        name="Suspend Zone",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key="manual_watering",
        name="Manual Watering",
        device_class=SwitchDeviceClass.SWITCH,
    ),
)


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    coordinator: HydrawiseDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    hydrawise: Hydrawiser = coordinator.api

    entities = []

    for zone in hydrawise.zones:
        for description in SWITCH_TYPES:
            entities.append(
                HydrawiseSwitch(
                    coordinator=coordinator,
                    controller_id=zone.controller_id,
                    zone_id=zone.id,
                    description=description,
                )
            )

    # Add all entities to HA
    async_add_entities(entities)


class HydrawiseSwitch(HydrawiseEntity, SwitchEntity):
    """A switch implementation for Hydrawise device."""

    def __init__(
        self,
        *,
        coordinator: HydrawiseDataUpdateCoordinator,
        controller_id: int,
        zone_id: int,
        description: EntityDescription,
    ) -> None:
        """Initiatlize."""
        super().__init__(
            coordinator=coordinator,
            controller_id=controller_id,
            zone_id=zone_id,
            description=description,
        )
        self.update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if self.entity_description.key == "manual_watering":
            # Watering Time needs to be passed if we want to override default
            await self.coordinator.api.async_run_zone(self.zone_id)
        elif self.entity_description.key == "suspend_zone":
            await self.coordinator.api.async_suspend_zone(
                self.zone_id, DEFAULT_SUSPEND_DAYS
            )

        self._attr_is_on = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if self.entity_description.key == "manual_watering":
            await self.coordinator.api.async_stop_zone(self.zone_id)
        elif self.entity_description.key == "suspend_zone":
            await self.coordinator.api.async_resume_zone(self.zone_id)

        self._attr_is_on = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update device state."""
        super()._handle_coordinator_update()

        self.update()

    def update(self) -> None:
        """Update state."""
        zone = self.coordinator.api.get_zone(self.zone_id)
        if zone is None:
            return

        LOGGER.debug(
            "Updating Watering switch for controller %d zone %s",
            self.controller_id,
            zone.name,
        )

        if self.entity_description.key == "manual_watering":
            self._attr_is_on = zone.scheduled_runs.current_run is not None
        elif self.entity_description.key == "suspend_zone":
            self._attr_is_on = zone.status.suspended_until is not None
