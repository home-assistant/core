"""Entity for the SleepIQ integration."""
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BED, ICON_OCCUPIED, SENSOR_TYPES
from .coordinator import SleepIQDataUpdateCoordinator


class SleepIQSensor(CoordinatorEntity):
    """Implementation of a SleepIQ sensor."""

    _attr_icon = ICON_OCCUPIED

    def __init__(
        self,
        coordinator: SleepIQDataUpdateCoordinator,
        bed_id: str,
        side: str,
        name: str,
    ) -> None:
        """Initialize the SleepIQ side entity."""
        super().__init__(coordinator)
        self.bed_id = bed_id
        self.side = side

        self._async_update_attrs()

        self._attr_name = f"SleepNumber {self.bed_data.name} {self.side_data.sleeper.first_name} {SENSOR_TYPES[name]}"
        self._attr_unique_id = (
            f"{self.bed_id}_{self.side_data.sleeper.first_name}_{name}"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        self.bed_data = self.coordinator.data[self.bed_id][BED]
        self.side_data = getattr(self.bed_data, self.side)
