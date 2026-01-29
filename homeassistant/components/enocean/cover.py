"""Support for EnOcean roller shutters."""

import asyncio
import logging
from typing import Any

from homeassistant_enocean.entity_id import EnOceanEntityID
from homeassistant_enocean.gateway import EnOceanHomeAssistantGateway

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_entry import EnOceanConfigEntry
from .entity import EnOceanEntity

_LOGGER = logging.getLogger(__name__)

# Constants for the 'movement stop' watchdog, probably to be refined in the future as user-definable options
WATCHDOG_TIMEOUT = 1
WATCHDOG_INTERVAL = 0.2
WATCHDOG_MAX_QUERIES = 10


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway = config_entry.runtime_data.gateway

    for entity_id in gateway.cover_entities:
        async_add_entities(
            [
                EnOceanCover(
                    entity_id,
                    gateway=gateway,
                    device_class=gateway.cover_entities[entity_id].device_class,
                ),
            ]
        )


class EnOceanCover(EnOceanEntity, CoverEntity):
    """Representation of an EnOcean cover."""

    def __init__(
        self,
        enocean_entity_id: EnOceanEntityID,
        gateway: EnOceanHomeAssistantGateway,
        device_class: CoverDeviceClass | None = None,
    ) -> None:
        """Initialize the EnOcean cover."""
        super().__init__(
            enocean_entity_id=enocean_entity_id,
            gateway=gateway,
        )
        self.gateway.register_cover_callback(enocean_entity_id, self.update)

        # set base class attributes
        self._attr_device_class = device_class or CoverDeviceClass.BLIND
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

        self._attr_is_closed: bool | None = None
        """Flag to indicate whether the cover is closed."""

        self.__stop_suspected = False
        """Flag to indicate that a stop of the cover movement is suspected."""

        self.__watchdog_enabled = False
        """Flag to indicate that the movement stop watchdog is enabled."""

        self.__watchdog_seconds_remaining: float = 0
        """Remaining seconds for the movement stop watchdog."""

        self.__watchdog_queries_remaining: int = 5
        """Remaining queries for the movement stop watchdog."""

    async def async_added_to_hass(self) -> None:
        """Query status after Home Assistant (re)start."""
        await super().async_added_to_hass()
        self.restart_watchdog()

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._attr_is_opening = True
        self._attr_is_closing = False
        self.gateway.set_cover_position(self.enocean_entity_id, 100)
        self.restart_watchdog()
        self.schedule_update_ha_state()

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._attr_is_opening = False
        self._attr_is_closing = True
        self.gateway.set_cover_position(self.enocean_entity_id, 0)
        self.restart_watchdog()
        self.schedule_update_ha_state()

    def set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        if ATTR_POSITION not in kwargs:
            return

        # determine opening/closing state
        if self._attr_current_cover_position is None:
            self._attr_is_opening = None
            self._attr_is_closing = None
        elif kwargs[ATTR_POSITION] == self._attr_current_cover_position:
            self._attr_is_opening = False
            self._attr_is_closing = False
        elif kwargs[ATTR_POSITION] > self._attr_current_cover_position:
            self._attr_is_opening = True
            self._attr_is_closing = False
        elif kwargs[ATTR_POSITION] < self._attr_current_cover_position:
            self._attr_is_opening = False
            self._attr_is_closing = True

        self.gateway.set_cover_position(self.enocean_entity_id, kwargs[ATTR_POSITION])
        self.restart_watchdog()
        self.schedule_update_ha_state()

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop any cover movement."""
        self.stop_watchdog()
        self._attr_is_opening = False
        self._attr_is_closing = False
        self.gateway.stop_cover(self.enocean_entity_id)
        self.schedule_update_ha_state()

    def update(self, new_position: int) -> None:
        """Update the cover state."""
        # upon receiving fully open/closed position, we assume the cover has stopped (without further querying)
        if new_position in (0, 100):
            self._attr_is_opening = False
            self._attr_is_closing = False
            self.stop_watchdog()

        elif self._attr_current_cover_position is not None:
            # upon receiving the same position as known, we suspect the cover has stopped and verify this by querying the status again (via watchdog)
            # upon receiving the same position again, we confirm the stop
            if new_position == self._attr_current_cover_position:
                if self.__stop_suspected:
                    self.__stop_suspected = False
                    self._attr_is_opening = False
                    self._attr_is_closing = False
                    self.stop_watchdog()
                else:
                    self.restart_watchdog()
                    self.__stop_suspected = True
                    return

            # depending on the known and new position, we set opening/closing state and restart the watchdog
            elif new_position > self._attr_current_cover_position:
                self._attr_is_opening = True
                self._attr_is_closing = False
                self.restart_watchdog()
            elif new_position < self._attr_current_cover_position:
                self._attr_is_opening = False
                self._attr_is_closing = True
                self.restart_watchdog()

        self._attr_current_cover_position = new_position

        # determine is_closed state
        if self._attr_current_cover_position == 0:
            self._attr_is_closed = True
        else:
            self._attr_is_closed = False

        self.schedule_update_ha_state()

    def restart_watchdog(self) -> None:
        """(Re)start the 'movement stop' watchdog."""
        self.__watchdog_seconds_remaining = WATCHDOG_TIMEOUT
        self.__watchdog_queries_remaining = WATCHDOG_MAX_QUERIES

        if self.__watchdog_enabled:
            return

        self.__watchdog_enabled = True
        self.hass.create_task(self.watchdog())

    def stop_watchdog(self) -> None:
        """Stop the 'movement stop' watchdog."""
        self.__watchdog_enabled = False

    async def watchdog(self) -> None:
        """Watchdog to check if the cover movement stopped.

        After watchdog time expired, the watchdog queries the current status.
        """

        while 1:
            await asyncio.sleep(WATCHDOG_INTERVAL)

            if not self.__watchdog_enabled:
                return

            if self.__watchdog_seconds_remaining <= 0:
                self.gateway.query_cover_position(self.enocean_entity_id)
                self.__watchdog_seconds_remaining = WATCHDOG_TIMEOUT
                self.__watchdog_queries_remaining -= 1

                if self.__watchdog_queries_remaining == 0:
                    _LOGGER.debug(
                        "'Movement stop' watchdog max query limit reached. Disabling watchdog and setting state to 'unknown'"
                    )
                    self._attr_current_cover_position = None
                    self._attr_is_closed = None
                    self._attr_is_opening = False
                    self._attr_is_closing = False
                    return
                continue

            self.__watchdog_seconds_remaining -= WATCHDOG_INTERVAL
