"""Support for Alpha2 heat control valve opening sensors."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import Alpha2BaseCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Alpha2 sensor entities from a config_entry."""

    coordinator: Alpha2BaseCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # HEATCTRL attribute ACTOR_PERCENT is not available in older firmware versions
    async_add_entities(
        Alpha2HeatControlValveOpeningSensor(coordinator, heat_control_id)
        for heat_control_id, heat_control in coordinator.data["heat_controls"].items()
        if heat_control["INUSE"]
        and heat_control["_HEATAREA_ID"]
        and heat_control.get("ACTOR_PERCENT") is not None
    )


class Alpha2HeatControlValveOpeningSensor(
    CoordinatorEntity[Alpha2BaseCoordinator], SensorEntity
):
    """Alpha2 heat control valve opening sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, coordinator: Alpha2BaseCoordinator, heat_control_id: str
    ) -> None:
        """Initialize Alpha2HeatControlValveOpeningSensor."""
        super().__init__(coordinator)
        self.heat_control_id = heat_control_id
        self._attr_unique_id = f"{heat_control_id}:valve_opening"
        heat_control = self.coordinator.data["heat_controls"][heat_control_id]
        heat_area = self.coordinator.data["heat_areas"][heat_control["_HEATAREA_ID"]]
        self._attr_name = (
            f"{heat_area['HEATAREA_NAME']} heat control {heat_control['NR']} valve"
            " opening"
        )

    @property
    def native_value(self) -> int:
        """Return the current valve opening percentage."""
        return self.coordinator.data["heat_controls"][self.heat_control_id][
            "ACTOR_PERCENT"
        ]
