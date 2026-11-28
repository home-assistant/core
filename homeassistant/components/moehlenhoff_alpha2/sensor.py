"""Support for Alpha2 heat control valve opening sensors."""

from typing import override

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import Alpha2BaseCoordinator, Alpha2ConfigEntry
from .entity import Alpha2RoomEntity

VALVE_OPENING_DESCRIPTION = SensorEntityDescription(
    key="valve_opening",
    translation_key="valve_opening",
    native_unit_of_measurement=PERCENTAGE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: Alpha2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Alpha2 sensor entities from a config_entry."""

    coordinator = config_entry.runtime_data

    # HEATCTRL attribute ACTOR_PERCENT is not available in older firmware versions
    async_add_entities(
        Alpha2HeatControlValveOpeningSensor(coordinator, heat_control_id)
        for heat_control_id, heat_control in coordinator.data["heat_controls"].items()
        if heat_control["INUSE"]
        and heat_control["_HEATAREA_ID"] in coordinator.data["heat_areas"]
        and heat_control.get("ACTOR_PERCENT") is not None
    )


class Alpha2HeatControlValveOpeningSensor(Alpha2RoomEntity, SensorEntity):
    """Alpha2 heat control valve opening sensor."""

    def __init__(
        self, coordinator: Alpha2BaseCoordinator, heat_control_id: str
    ) -> None:
        """Initialize Alpha2HeatControlValveOpeningSensor."""
        heat_control = coordinator.data["heat_controls"][heat_control_id]
        super().__init__(coordinator, heat_control["_HEATAREA_ID"])
        self.entity_description = VALVE_OPENING_DESCRIPTION
        self._attr_translation_placeholders = {"number": str(heat_control["NR"])}
        self.heat_control_id = heat_control_id
        self._attr_unique_id = f"{heat_control_id}:valve_opening"

    @property
    @override
    def native_value(self) -> int:
        """Return the current valve opening percentage."""
        return self.coordinator.data["heat_controls"][self.heat_control_id][
            "ACTOR_PERCENT"
        ]
