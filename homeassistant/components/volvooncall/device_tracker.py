"""Support for tracking a Volvo."""

from __future__ import annotations

from volvooncall.dashboard import Instrument

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VOLVO_DISCOVERY_NEW
from .coordinator import VolvoUpdateCoordinator
from .entity import VolvoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure device_trackers from a config entry created in the integrations UI."""
    coordinator: VolvoUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    volvo_data = coordinator.volvo_data

    @callback
    def async_discover_device(instruments: list[Instrument]) -> None:
        """Discover and add a discovered Volvo On Call device tracker."""
        async_add_entities(
            VolvoTrackerEntity(
                instrument.vehicle.vin,
                instrument.component,
                instrument.attr,
                instrument.slug_attr,
                coordinator,
            )
            for instrument in instruments
            if instrument.component == "device_tracker"
        )

    async_discover_device([*volvo_data.instruments])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VOLVO_DISCOVERY_NEW, async_discover_device)
    )


class VolvoTrackerEntity(VolvoEntity, TrackerEntity):
    """A tracked Volvo vehicle."""

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        latitude, _ = self._get_pos()
        return latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        _, longitude = self._get_pos()
        return longitude

    def _get_pos(self) -> tuple[float, float]:
        volvo_data = self.coordinator.volvo_data
        instrument = volvo_data.instrument(
            self.vin, self.component, self.attribute, self.slug_attr
        )

        latitude, longitude, _, _, _ = instrument.state

        return (float(latitude), float(longitude))
