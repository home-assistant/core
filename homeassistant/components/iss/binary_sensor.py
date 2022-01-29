"""Support for iss binary sensor."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_NAME,
    CONF_SHOW_ON_MAP,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import IssData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_ISS_NEXT_RISE = "next_rise"
ATTR_ISS_NUMBER_PEOPLE_SPACE = "number_of_people_in_space"

DEFAULT_NAME = "ISS"
DEFAULT_DEVICE_CLASS = "visible"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SHOW_ON_MAP, default=False): cv.boolean,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import ISS configuration from yaml."""
    _LOGGER.warning(
        "Configuration of the iss platform in YAML is deprecated and will be "
        "removed in Home Assistant 2022.5; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: DataUpdateCoordinator[IssData] = hass.data[DOMAIN]

    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    show_on_map = entry.data.get(CONF_SHOW_ON_MAP, False)

    async_add_entities([IssBinarySensor(coordinator, name, show_on_map)], True)


class IssBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Implementation of the ISS binary sensor."""

    _attr_device_class = DEFAULT_DEVICE_CLASS
    coordinator: DataUpdateCoordinator[IssData]

    def __init__(
        self, coordinator: DataUpdateCoordinator[IssData], name: str, show: bool
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._state = None
        self._attr_name = name
        self._show_on_map = show

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.coordinator.data["is_above"] is True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs = {
            ATTR_ISS_NUMBER_PEOPLE_SPACE: self.coordinator.data[
                "number_of_people_in_space"
            ],
            ATTR_ISS_NEXT_RISE: self.coordinator.data["next_rise"],
        }
        if self._show_on_map:
            attrs[ATTR_LONGITUDE] = self.coordinator.data["current_location"].get(
                "longitude"
            )
            attrs[ATTR_LATITUDE] = self.coordinator.data["current_location"].get(
                "latitude"
            )
        else:
            attrs["long"] = self.coordinator.data["current_location"].get("longitude")
            attrs["lat"] = self.coordinator.data["current_location"].get("latitude")

        return attrs
