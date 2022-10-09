"""Sensor entities for PJLink integration."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PJLinkUpdateCoordinator
from .entity import PJLinkEntity

LAMP_HOURS_SENSOR = SensorEntityDescription(
    key="lamp_hours",
    name="Lamp Hours",
    entity_category=EntityCategory.DIAGNOSTIC,
    device_class=SensorDeviceClass.DURATION,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PJLink from a config entry."""
    domain_data = hass.data[DOMAIN]
    coordinator: PJLinkUpdateCoordinator = domain_data[entry.entry_id]

    entities: list[PJLinkEntity] = []

    # Create lamp entities
    for lamp_idx in range(coordinator.device.lamp_count):
        entities.append(
            PJLinkLampHoursSensorEntity(coordinator=coordinator, lamp_idx=lamp_idx)
        )

    async_add_entities(entities)


class PJLinkLampHoursSensorEntity(PJLinkEntity, SensorEntity):
    """PJLink lamp hours state sensor."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "hours"

    def __init__(self, coordinator: PJLinkUpdateCoordinator, lamp_idx: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        description = LAMP_HOURS_SENSOR

        self.lamp_index = lamp_idx

        self.entity_description = description
        self._attr_name = description.name
        self._attr_unique_id = (
            f"{coordinator.projector_unique_id}_lamp_{lamp_idx}_hours"
        )
        self._async_update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Handle coordinator updates."""
        self._attr_native_value = self.device.async_get_lamp_state(self.lamp_index)[
            "hours"
        ]
