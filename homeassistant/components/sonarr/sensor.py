"""Support for Sonarr sensors."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_GIGABYTES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SonarrDataUpdateCoordinator
from .entity import SonarrEntity

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="commands",
        name="Sonarr Commands",
        icon="mdi:code-braces",
        native_unit_of_measurement="Commands",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="diskspace",
        name="Sonarr Disk Space",
        icon="mdi:harddisk",
        native_unit_of_measurement=DATA_GIGABYTES,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="queue",
        name="Sonarr Queue",
        icon="mdi:download",
        native_unit_of_measurement="Episodes",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="series",
        name="Sonarr Shows",
        icon="mdi:television",
        native_unit_of_measurement="Series",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="upcoming",
        name="Sonarr Upcoming",
        icon="mdi:television",
        native_unit_of_measurement="Episodes",
    ),
    SensorEntityDescription(
        key="wanted",
        name="Sonarr Wanted",
        icon="mdi:television",
        native_unit_of_measurement="Episodes",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sonarr sensors based on a config entry."""
    coordinator: SonarrDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        SonarrSensor(coordinator, entry.entry_id, description)
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities, True)


class SonarrSensor(SonarrEntity, SensorEntity):
    """Implementation of the Sonarr sensor."""

    def __init__(
        self,
        coordinator: SonarrDataUpdateCoordinator,
        entry_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize Sonarr sensor."""
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"

        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            device_id=entry_id,
        )

    async def async_update(self) -> None:
        """Update the entity."""
        if not self.enabled:
            return

        if self.entity_description.key not in ("diskspace"):
            self.coordinator.enable_datapoint(self.entity_description.key)

        await super().async_update()

    async def async_will_remove_from_hass(self) -> None:
        """Disable additional datapoint for sensor data."""
        if self.entity_description.key not in ("diskspace"):
            self.coordinator.disable_datapoint(self.entity_description.key)

        await super().async_will_remove_from_hass()

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes of the entity."""
        attrs = {}
        key = self.entity_description.key
        app = self.coordinator.sonarr.app

        if key == "diskspace":
            for disk in app.disks:
                free = disk.free / 1024 ** 3
                total = disk.total / 1024 ** 3
                usage = free / total * 100

                attrs[
                    disk.path
                ] = f"{free:.2f}/{total:.2f}{self.unit_of_measurement} ({usage:.2f}%)"
        elif key == "commands" and self.coordinator.data.get("commands") is not None:
            for command in self.coordinator.data["commands"]:
                attrs[command.name] = command.state
        elif key == "queue" and self.coordinator.data.get("queue") is not None:
            for item in self.coordinator.data["queue"]:
                remaining = 1 if item.size == 0 else item.size_remaining / item.size
                remaining_pct = 100 * (1 - remaining)
                name = f"{item.episode.series.title} {item.episode.identifier}"
                attrs[name] = f"{remaining_pct:.2f}%"
        elif key == "series" and self.coordinator.data.get("series") is not None:
            for item in self.coordinator.data["series"]:
                attrs[item.series.title] = f"{item.downloaded}/{item.episodes} Episodes"
        elif key == "upcoming" and self.coordinator.data.get("upcoming") is not None:
            for episode in self.coordinator.data["upcoming"]:
                attrs[episode.series.title] = episode.identifier
        elif key == "wanted" and self.coordinator.data.get("wanted") is not None:
            for episode in self.coordinator.data["wanted"].episodes:
                name = f"{episode.series.title} {episode.identifier}"
                attrs[name] = episode.airdate

        return attrs

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        key = self.entity_description.key
        app = self.coordinator.sonarr.app

        if key == "diskspace":
            total_free = sum(disk.free for disk in app.disks)
            free = total_free / 1024 ** 3
            return f"{free:.2f}"

        if key == "commands" and self.coordinator.data.get("commands") is not None:
            return len(self.coordinator.data["commands"])

        if key == "queue" and self.coordinator.data.get("queue") is not None:
            return len(self.coordinator.data["queue"])

        if key == "series" and self.coordinator.data.get("series") is not None:
            return len(self.coordinator.data["series"])

        if key == "upcoming" and self.coordinator.data.get("upcoming") is not None:
            return len(self.coordinator.data["upcoming"])

        if key == "wanted" and self.coordinator.data.get("wanted") is not None:
            return self.coordinator.data["wanted"].total

        return None
