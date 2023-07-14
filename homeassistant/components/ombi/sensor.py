"""Support for Ombi."""
from __future__ import annotations

from datetime import timedelta
import logging

from pyombi import OmbiError

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Ombi sensor platform."""
    if discovery_info is None:
        return

    ombi = hass.data[DOMAIN]["instance"]

    entities = [OmbiSensor(ombi, description) for description in SENSOR_TYPES]

    add_entities(entities, True)


class OmbiSensor(SensorEntity):
    """Representation of an Ombi sensor."""

    def __init__(self, ombi, description: SensorEntityDescription) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._ombi = ombi

        self._attr_name = f"Ombi {description.name}"

    def update(self) -> None:
        """Update the sensor."""
        try:
            sensor_type = self.entity_description.key
            if sensor_type == "movies":
                self._attr_native_value = self._ombi.movie_requests
            elif sensor_type == "tv":
                self._attr_native_value = self._ombi.tv_requests
            elif sensor_type == "music":
                self._attr_native_value = self._ombi.music_requests
            elif sensor_type == "pending":
                self._attr_native_value = self._ombi.total_requests["pending"]
            elif sensor_type == "approved":
                self._attr_native_value = self._ombi.total_requests["approved"]
            elif sensor_type == "available":
                self._attr_native_value = self._ombi.total_requests["available"]
        except OmbiError as err:
            _LOGGER.warning("Unable to update Ombi sensor: %s", err)
            self._attr_native_value = None
