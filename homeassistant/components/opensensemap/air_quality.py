"""Support for openSenseMap Air Quality data."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.air_quality import PLATFORM_SCHEMA, AirQualityEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_STATION_ID, DOMAIN, MANUFACTURER
from .coordinator import OpenSenseMapDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_STATION_ID): cv.string, vol.Optional(CONF_NAME): cv.string}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the openSenseMap air quality platform."""

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize the entries."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [OpenSenseMapQuality(coordinator, entry)],
    )


class OpenSenseMapQuality(
    CoordinatorEntity[OpenSenseMapDataUpdateCoordinator], AirQualityEntity
):
    """Implementation of an openSenseMap air quality entity."""

    _attr_attribution = "Data provided by openSenseMap"
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, coordinator: OpenSenseMapDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the air quality entity."""
        super().__init__(coordinator)

        self._name = config_entry.data[CONF_NAME]
        self._station_id = config_entry.data[CONF_STATION_ID]
        self._attr_unique_id = f"{self._station_id}_air_quality"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._station_id)},
            manufacturer=MANUFACTURER,
            name=self._name,
        )

    @property
    def particulate_matter_2_5(self) -> float | None:
        """Return the particulate matter 2.5 level."""
        return self.coordinator.data.pm2_5

    @property
    def particulate_matter_10(self) -> float | None:
        """Return the particulate matter 10 level."""
        return self.coordinator.data.pm10
