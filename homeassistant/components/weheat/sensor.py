"""Platform for sensor integration."""

from decimal import Decimal

from weheat_backend_client.abstractions.heat_pump import HeatPump

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SENSORS
from .coordinator import WeheatDataUpdateCoordinator
from .entity import WeheatEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors for weheat heat pump."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        WeheatHeatPumpSensor(
            coordinator=coordinator, entity_description=entity_description
        )
        for entity_description in SENSORS
        if hasattr(HeatPump, entity_description.key)
    )


class WeheatHeatPumpSensor(WeheatEntity, SensorEntity):
    """An entity using CoordinatorEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available

    """

    def __init__(
        self, coordinator: WeheatDataUpdateCoordinator, entity_description
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self.entity_description = entity_description

        self._attr_unique_id = (
            coordinator.heatpump_id + "_" + self.entity_description.key
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        if self.coordinator.data is None or self.entity_description.key == "":
            self._attr_native_value = Decimal(0)
        else:
            self._attr_native_value = getattr(
                self.coordinator.data, self.entity_description.key
            )
        self.async_write_ha_state()
