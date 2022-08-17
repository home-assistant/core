"""Alert sensors."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FLUME_AUTH,
    NOTIFICATION_BRIDGE_DISCONNECT,
    NOTIFICATION_HIGH_FLOW,
    NOTIFICATION_LEAK_DETECTED,
)
from .coordinator import FlumeNotificationDataUpdateCoordinator
from .entity import FlumeEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class FlumeBinarySensorRequiredKeysMixin:
    """Mixin for required keys."""

    event_rule: str


@dataclass
class FlumeBinarySensorEntityDescription(
    BinarySensorEntityDescription, FlumeBinarySensorRequiredKeysMixin
):
    """Describes a binary sensor entity."""


FLUME_BINARY_SENSORS: tuple[FlumeBinarySensorEntityDescription, ...] = (
    FlumeBinarySensorEntityDescription(
        key="leak",
        name="Leak detected",
        event_rule=NOTIFICATION_LEAK_DETECTED,
        icon="mdi:pipe-leak",
    ),
    FlumeBinarySensorEntityDescription(
        key="flow",
        name="High flow",
        event_rule=NOTIFICATION_HIGH_FLOW,
        icon="mdi:waves",
    ),
    FlumeBinarySensorEntityDescription(
        key="bridge",
        name="Bridge disconnected",
        event_rule=NOTIFICATION_BRIDGE_DISCONNECT,
        icon="mdi:bridge",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Flume binary sensor.."""

    flume_domain_data = hass.data[DOMAIN][config_entry.entry_id]
    flume_auth = flume_domain_data[FLUME_AUTH]

    coordinator = FlumeNotificationDataUpdateCoordinator(hass=hass, auth=flume_auth)

    async_add_entities(
        FlumeBinarySensor(coordinator=coordinator, description=description)
        for description in FLUME_BINARY_SENSORS
    )


class FlumeBinarySensor(FlumeEntity, BinarySensorEntity):
    """Binary sensor class."""

    entity_description: FlumeBinarySensorEntityDescription

    _attr_has_entity_name = True

    @property
    def is_on(self) -> bool:
        """Return on state."""
        rule = self.entity_description.event_rule
        _LOGGER.debug("Checking value for %s", rule)
        return rule in self.coordinator.active_notification_types
