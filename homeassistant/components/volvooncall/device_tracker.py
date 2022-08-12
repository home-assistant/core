"""Support for tracking a Volvo."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, VolvoEntity, VolvoUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure device_trackers from a config entry created in the integrations UI."""
    volvo_data = hass.data[DOMAIN][config_entry.entry_id].volvo_data
    for instrument in volvo_data.instruments:
        if instrument.component == "device_tracker":
            discovery_info = (
                instrument.vehicle.vin,
                instrument.component,
                instrument.attr,
                instrument.slug_attr,
            )

            async_add_entities(
                [
                    VolvoTrackerEntity(
                        hass.data[DOMAIN][config_entry.entry_id], *discovery_info
                    )
                ]
            )


class VolvoTrackerEntity(VolvoEntity, TrackerEntity):
    """A tracked Volvo vehicle."""

    def __init__(
        self,
        coordinator: VolvoUpdateCoordinator,
        vin: str,
        component: str,
        attribute: str,
        slug_attr: str,
    ) -> None:
        """Initialize the lock."""
        super().__init__(vin, component, attribute, slug_attr, coordinator)

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        latitude, _ = self._get_pos()
        return float(latitude)

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        _, longitude = self._get_pos()
        return float(longitude)

    @property
    def source_type(self) -> SourceType | str:
        """Return the source type (GPS)."""
        return SourceType.GPS

    def _get_pos(self) -> tuple[float, float]:
        volvo_data = self.coordinator.volvo_data
        instrument = volvo_data.instrument(
            self.vin, self.component, self.attribute, self.slug_attr
        )

        latitude, longitude, _, _, _ = instrument.state

        return (float(latitude), float(longitude))
