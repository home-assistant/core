"""Support for Hydrawise sprinkler sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER
from .coordinator import HydrawiseDataUpdateCoordinator, HydrawiseEntity
from .hydrawiser import Hydrawiser

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="next_cycle",
        name="Next Cycle",
        device_class=SensorDeviceClass.DATE,
    ),
    SensorEntityDescription(
        key="watering_time",
        name="Watering Time",
        icon="mdi:water-pump",
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
)

TWO_YEAR_SECONDS = 60 * 60 * 24 * 365 * 2
WATERING_TIME_ICON = "mdi:water-pump"


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
            for description in SENSOR_TYPES:
                entities.append(
                    HydrawiseSensor(
                        coordinator=coordinator,
                        controller_id=controller.controller_id,
                        relay_id=relay.relay_id,
                        description=description,
                    )
                )

    # Add all entities to HA
    async_add_entities(entities)


class HydrawiseSensor(HydrawiseEntity, SensorEntity):
    """A sensor implementation for Hydrawise device."""

    def __init__(
        self,
        *,
        coordinator: HydrawiseDataUpdateCoordinator,
        controller_id: int,
        relay_id: int,
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator=coordinator,
            controller_id=controller_id,
            relay_id=relay_id,
            description=description,
        )
        self.update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        super()._handle_coordinator_update()

        self.update()

    def update(self) -> None:
        """Update state."""
        relay = self.coordinator.api.get_relay(self.controller_id, self.relay_id)
        if relay is None:
            return

        if self.entity_description.key == "watering_time":
            self._attr_native_value = relay.time_remaining()
            LOGGER.debug(
                "Updating WateringTime sensor for controller %d zone %s, remaining time %ds",
                self.controller_id,
                relay.name,
                self._attr_native_value,
            )
        else:  # _sensor_type == 'next_cycle'
            if relay.timestr == "":
                self._attr_native_value = None
            else:
                self._attr_native_value = dt_util.utc_from_timestamp(
                    dt_util.as_timestamp(dt_util.now()) + relay.time
                )

            LOGGER.debug(
                "Updating NextCycle sensor for controller %s zone %s, next cycle %s",
                self.controller_id,
                relay.name,
                self._attr_native_value,
            )
