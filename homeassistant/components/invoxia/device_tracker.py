"""Platform for invoxia.device_tracker integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from gps_tracker import AsyncClient, Tracker
from gps_tracker.client.datatypes import Tracker01

from homeassistant.components import device_tracker
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITIES
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CLIENT, DOMAIN, LOGGER, MDI_ICONS
from .coordinator import GpsTrackerCoordinator
from .helpers import GpsTrackerData

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the device_tracker platform."""
    client: AsyncClient = hass.data[DOMAIN][entry.entry_id][CLIENT]
    trackers: list[Tracker] = await client.get_trackers()

    coordinators = [
        GpsTrackerCoordinator(hass, client, tracker) for tracker in trackers
    ]

    await asyncio.gather(
        *[
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators
        ]
    )

    entities = [
        GpsTrackerEntity(coordinator, client, tracker)
        for tracker, coordinator in zip(trackers, coordinators)
    ]

    hass.data[DOMAIN][entry.entry_id][CONF_ENTITIES].extend(entities)
    async_add_entities(entities, update_before_add=True)


@dataclass(frozen=True)
class GpsTrackerEntityDescription(EntityDescription):
    """Describes a Invoxia GPS tracker entity."""


class GpsTrackerEntity(
    CoordinatorEntity[GpsTrackerCoordinator], device_tracker.TrackerEntity
):
    """Class for Invoxia™ GPS tracker devices."""

    entity_description: GpsTrackerEntityDescription

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False

    def __init__(
        self, coordinator: GpsTrackerCoordinator, client: AsyncClient, tracker: Tracker
    ) -> None:
        """Store tracker main properties."""
        super().__init__(coordinator)

        # Attributes for update logic
        self._client: AsyncClient = client
        self._tracker: Tracker = tracker

        # Static entity attributes
        if isinstance(tracker, Tracker01):
            self._attr_icon = MDI_ICONS[tracker.tracker_config.icon]
            self._attr_name = self._tracker.name
            self._attr_unique_id = str(self._tracker.id)

        self.entity_description = GpsTrackerEntityDescription(
            entity_registry_enabled_default=True,
            has_entity_name=True,
            key="invoxia_gps_tracker",
            translation_key="invoxia_gps_tracker",
            icon=self._attr_icon,
        )

        # Dynamic entity attributes
        self._attr_available: bool = True

        # Dynamic tracker-entity attributes
        self._tracker_data = GpsTrackerData(
            latitude=0.0,
            longitude=0.0,
            accuracy=0,
            battery=0,
        )
        self._update_attr()

    def _update_attr(self) -> None:
        """Update dynamic attributes."""
        LOGGER.debug("Updating attributes of Tracker %u", self._tracker.id)
        self._tracker_data = self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_attr()
        return super()._handle_coordinator_update()

    @property
    def battery_level(self) -> int | None:
        """Return tracker battery level."""
        return self._tracker_data.battery

    @property
    def source_type(self) -> str:
        """Define source type as being GPS."""
        return device_tracker.SourceType.GPS

    @property
    def location_accuracy(self) -> int:
        """Return accuration of last location data."""
        return self._tracker_data.accuracy

    @property
    def latitude(self) -> float | None:
        """Return last device latitude."""
        return self._tracker_data.latitude

    @property
    def longitude(self) -> float | None:
        """Return last device longitude."""
        return self._tracker_data.longitude
