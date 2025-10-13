"""Binary sensor platform for Squeezebox integration."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SqueezeboxConfigEntry, SqueezeBoxPlayerUpdateCoordinator
from .const import (
    PLAYER_SENSOR_ALARM_ACTIVE,
    PLAYER_SENSOR_ALARM_SNOOZE,
    PLAYER_SENSOR_ALARM_UPCOMING,
    SIGNAL_PLAYER_DISCOVERED,
    STATUS_SENSOR_NEEDSRESTART,
    STATUS_SENSOR_RESCAN,
)
from .entity import LMSStatusEntity, SqueezeboxEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

SERVER_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=STATUS_SENSOR_RESCAN,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key=STATUS_SENSOR_NEEDSRESTART,
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

PLAYER_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=PLAYER_SENSOR_ALARM_UPCOMING,
    ),
    BinarySensorEntityDescription(
        key=PLAYER_SENSOR_ALARM_ACTIVE,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key=PLAYER_SENSOR_ALARM_SNOOZE,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SqueezeboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Platform setup using common elements."""

    # Add player sensor entities when player discovered
    async def _player_discovered(
        player_coordinator: SqueezeBoxPlayerUpdateCoordinator,
    ) -> None:
        _LOGGER.debug(
            "Setting up binary sensor entities for player %s, model %s",
            player_coordinator.player.name,
            player_coordinator.player.model,
        )

        async_add_entities(
            SqueezeboxBinarySensorEntity(player_coordinator, description)
            for description in PLAYER_SENSORS
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_PLAYER_DISCOVERED, _player_discovered)
    )
    async_add_entities(
        ServerStatusBinarySensor(entry.runtime_data.coordinator, description)
        for description in SERVER_SENSORS
    )


class ServerStatusBinarySensor(LMSStatusEntity, BinarySensorEntity):
    """LMS Status based sensor from LMS via coordinator."""

    @property
    def is_on(self) -> bool:
        """LMS Status directly from coordinator data."""
        return bool(self.coordinator.data[self.entity_description.key])


class SqueezeboxBinarySensorEntity(SqueezeboxEntity, BinarySensorEntity):
    """Representation of player based binary sensors."""

    description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SqueezeBoxPlayerUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the SqueezeBox sensor."""
        super().__init__(coordinator)
        self.description = description
        self._attr_translation_key = description.key.replace(" ", "_")
        self._attr_unique_id = f"{format_mac(self._player.player_id)}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return bool(getattr(self.coordinator.player, self.description.key, None))
