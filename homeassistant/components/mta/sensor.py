"""Sensor platform for MTA New York City Transit."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_LINE, CONF_STOP_ID, CONF_STOP_NAME, DOMAIN
from .coordinator import MTAConfigEntry, MTADataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MTAConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MTA sensor based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities([MTAArrivalSensor(coordinator, entry)])


class MTAArrivalSensor(CoordinatorEntity[MTADataUpdateCoordinator], SensorEntity):
    """Sensor that displays next MTA train arrival time."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_arrival"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:subway-variant"

    def __init__(
        self, coordinator: MTADataUpdateCoordinator, entry: MTAConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        line = entry.data[CONF_LINE]
        stop_id = entry.data[CONF_STOP_ID]
        stop_name = entry.data.get(CONF_STOP_NAME, stop_id)
        self._stop_id = stop_id
        self._attr_unique_id = f"{entry.entry_id}_next_arrival"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"{line} Line - {stop_name}",
            manufacturer="MTA",
            model="Subway",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if not self.coordinator.data.arrivals:
            return None

        # Minutes until next arrival
        return self.coordinator.data.arrivals[0].minutes_until

    @property
    def extra_state_attributes(self) -> dict[str, str | list]:
        """Return additional attributes."""
        arrivals = self.coordinator.data.arrivals
        attrs: dict[str, str | list] = {}
        attrs["stop_id"] = self._stop_id

        attrs["arrivals"] = [
            {
                "route": arrival.route_id,
                "destination": arrival.destination,
                "minutes_until": arrival.minutes_until,
                "arrival_time": arrival.arrival_time.isoformat(),
            }
            for arrival in arrivals
        ]

        return attrs
