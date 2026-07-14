"""Support for non-delivered packages recorded in AfterShip."""

import logging
from typing import Any, Final, override

from pyaftership import AfterShip, AfterShipException

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import Throttle

from . import AfterShipConfigEntry
from .const import (
    ATTR_TRACKINGS,
    ATTRIBUTION,
    BASE,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
    UPDATE_TOPIC,
)

_LOGGER: Final = logging.getLogger(__name__)

PLATFORM_SCHEMA: Final = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AfterShipConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AfterShip sensor entities based on a config entry."""
    aftership = config_entry.runtime_data

    async_add_entities([AfterShipSensor(aftership, config_entry.title)], True)


class AfterShipSensor(SensorEntity):
    """Representation of a AfterShip sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_native_unit_of_measurement: str = "packages"
    _attr_translation_key = "packages"

    def __init__(self, aftership: AfterShip, name: str) -> None:
        """Initialize the sensor."""
        self._attributes: dict[str, Any] = {}
        self._state: int | None = None
        self.aftership = aftership
        self._attr_name = name

    @property
    @override
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self._state

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str]:
        """Return attributes for the sensor."""
        return self._attributes

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, UPDATE_TOPIC, self._force_update)
        )

    async def _force_update(self) -> None:
        """Force update of data."""
        await self.async_update(no_throttle=True)
        self.async_write_ha_state()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self, **kwargs: Any) -> None:
        """Get the latest data from the AfterShip API."""
        try:
            trackings = await self.aftership.trackings.list()
        except AfterShipException as err:
            _LOGGER.error("Errors when querying AfterShip - %s", err)
            return

        status_to_ignore = {"delivered"}
        status_counts: dict[str, int] = {}
        parsed_trackings = []
        not_delivered_count = 0

        for track in trackings["trackings"]:
            status = track["tag"].lower()
            name = (
                track["tracking_number"] if track["title"] is None else track["title"]
            )
            last_checkpoint = (
                f"Shipment {track['tag'].lower()}"
                if not track["checkpoints"]
                else track["checkpoints"][-1]
            )
            status_counts[status] = status_counts.get(status, 0) + 1
            parsed_trackings.append(
                {
                    "name": name,
                    "tracking_number": track["tracking_number"],
                    "slug": track["slug"],
                    "link": f"{BASE}{track['slug']}/{track['tracking_number']}",
                    "last_update": track["updated_at"],
                    "expected_delivery": track["expected_delivery"],
                    "status": track["tag"],
                    "last_checkpoint": last_checkpoint,
                }
            )

            if status not in status_to_ignore:
                not_delivered_count += 1
            else:
                _LOGGER.debug("Ignoring %s as it has status: %s", name, status)

        self._attributes = {
            **status_counts,
            ATTR_TRACKINGS: parsed_trackings,
        }

        self._state = not_delivered_count
