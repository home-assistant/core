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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_WATERING_TIME,
    DOMAIN,
    LOGGER,
)
from .coordinator import HydrawiseDataUpdateCoordinator, HydrawiseEntity
from .hydrawiser import Hydrawiser

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="auto_watering",
        name="Automatic Watering",
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

    for controller in hydrawise.controllers:
        for relay in controller.relays:
            for description in SWITCH_TYPES:
                entities.append(
                    HydrawiseSwitch(
                        coordinator=coordinator,
                        controller_id=controller.controller_id,
                        relay_id=relay.relay_id,
                        description=description,
                    )
                )

    # Add all entities to HA
    async_add_entities(entities)


class HydrawiseSwitch(HydrawiseEntity, SwitchEntity):
    """A switch implementation for Hydrawise device."""

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        relay = self.coordinator.api.get_relay(self.controller_id, self.relay_id)
        if relay is None:
            return

        if self.entity_description.key == "manual_watering":
            # Watering Time needs to be passed
            self.coordinator.api.run_zone(DEFAULT_WATERING_TIME, relay)
        elif self.entity_description.key == "auto_watering":
            self.coordinator.api.suspend_zone(0, relay)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        relay = self.coordinator.api.get_relay(self.controller_id, self.relay_id)
        if relay is None:
            return

        if self.entity_description.key == "manual_watering":
            self.coordinator.api.run_zone(0, relay)
        elif self.entity_description.key == "auto_watering":
            self.coordinator.api.suspend_zone(365, relay)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update device state."""
        super()._handle_coordinator_update()

        relay = self.coordinator.api.get_relay(self.controller_id, self.relay_id)
        if relay is None:
            return

        LOGGER.debug(
            "Updating Watering switch for controller %d zone %s, timestr %s",
            self.controller_id,
            relay.name,
            relay.timestr,
        )

        if self.entity_description.key == "manual_watering":
            self._attr_is_on = relay.time == 1
        elif self.entity_description.key == "auto_watering":
            self._attr_is_on = relay.timestr not in {"", "Now"}
