"""Support for ReCollect Waste sensors."""
from __future__ import annotations

from aiorecollect.client import PickupType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FRIENDLY_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_PLACE_ID, CONF_SERVICE_ID, DOMAIN, LOGGER

ATTR_PICKUP_TYPES = "pickup_types"
ATTR_AREA_NAME = "area_name"

SENSOR_TYPE_CURRENT_PICKUP = "current_pickup"
SENSOR_TYPE_NEXT_PICKUP = "next_pickup"

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=SENSOR_TYPE_CURRENT_PICKUP,
        name="Current pickup",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_NEXT_PICKUP,
        name="Next pickup",
    ),
)


@callback
def async_get_pickup_type_names(
    entry: ConfigEntry, pickup_types: list[PickupType]
) -> list[str]:
    """Return proper pickup type names from their associated objects."""
    return [
        t.friendly_name
        if entry.options.get(CONF_FRIENDLY_NAME) and t.friendly_name
        else t.name
        for t in pickup_types
    ]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ReCollect Waste sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ReCollectWasteSensor(coordinator, entry, description)
            for description in SENSOR_DESCRIPTIONS
        ]
    )


class ReCollectWasteSensor(CoordinatorEntity, SensorEntity):
    """ReCollect Waste Sensor."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._attr_extra_state_attributes = {}
        self._attr_unique_id = f"{entry.data[CONF_PLACE_ID]}_{entry.data[CONF_SERVICE_ID]}_{description.key}"
        self._entry = entry
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Respond to a DataUpdateCoordinator update."""
        self.update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if self.entity_description.key == SENSOR_TYPE_CURRENT_PICKUP:
            try:
                event = self.coordinator.data[0]
            except IndexError:
                LOGGER.error("No current pickup found")
                return
        else:
            try:
                event = self.coordinator.data[1]
            except IndexError:
                LOGGER.info("No next pickup found")
                return

        self._attr_extra_state_attributes.update(
            {
                ATTR_PICKUP_TYPES: async_get_pickup_type_names(
                    self._entry, event.pickup_types
                ),
                ATTR_AREA_NAME: event.area_name,
            }
        )
        self._attr_native_value = event.date
