"""Support for Streamlabs Water Monitor Away Mode."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, StreamlabsCoordinator

DEPENDS = ["streamlabswater"]

MIN_TIME_BETWEEN_LOCATION_UPDATES = timedelta(seconds=60)

ATTR_LOCATION_ID = "location_id"
NAME_AWAY_MODE = "Water Away Mode"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_devices: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the StreamLabsWater mode sensor."""
    coordinator = hass.data[DOMAIN]

    add_devices([StreamlabsAwayMode(coordinator)])


class StreamlabsAwayMode(CoordinatorEntity[StreamlabsCoordinator], BinarySensorEntity):
    """Monitor the away mode state."""

    @property
    def name(self) -> str:
        """Return the name for away mode."""
        return f"{self.coordinator.location_name} {NAME_AWAY_MODE}"

    @property
    def is_on(self) -> bool:
        """Return if away mode is on."""
        return self.coordinator.data.is_away
