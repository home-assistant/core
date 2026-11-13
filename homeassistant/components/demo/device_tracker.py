"""Demo platform for the Device tracker component."""

import random
from typing import override

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SIGNAL_RANDOMIZE_DEVICE_TRACKER_DATA


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo trackers."""
    async_add_entities(
        [
            DemoRandomTracker(hass, "demo_paulus", "Paulus"),
            DemoRandomTracker(hass, "demo_anne_therese", "Anne Therese"),
            DemoTracker(
                "demo_home_boy",
                "Home Boy",
                hass.config.latitude - 0.00002,
                hass.config.longitude + 0.00002,
                20,
            ),
        ]
    )


def _offset() -> float:
    """Return random offset."""
    return random.randrange(500, 2000) / 2e5 * random.choice((-1, 1))


def _random_location(hass: HomeAssistant) -> tuple[float, float, int]:
    """Return a random location around home and its accuracy."""
    return (
        hass.config.latitude + _offset(),
        hass.config.longitude + _offset(),
        random.randrange(50, 150),
    )


class DemoTracker(TrackerEntity):
    """Representation of a demo tracker at a fixed location."""

    def __init__(
        self,
        unique_id: str,
        name: str,
        latitude: float,
        longitude: float,
        location_accuracy: float,
    ) -> None:
        """Initialize the tracker."""
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_latitude = latitude
        self._attr_longitude = longitude
        self._attr_location_accuracy = location_accuracy


class DemoRandomTracker(DemoTracker):
    """Representation of a demo tracker moved by the randomize action."""

    def __init__(self, hass: HomeAssistant, unique_id: str, name: str) -> None:
        """Initialize the tracker at a random location."""
        super().__init__(unique_id, name, *_random_location(hass))

    @override
    async def async_added_to_hass(self) -> None:
        """Listen to the randomize action."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_RANDOMIZE_DEVICE_TRACKER_DATA, self._async_randomize
            )
        )

    @callback
    def _async_randomize(self) -> None:
        """Move the tracker to a new random location."""
        (
            self._attr_latitude,
            self._attr_longitude,
            self._attr_location_accuracy,
        ) = _random_location(self.hass)
        self.async_write_ha_state()
