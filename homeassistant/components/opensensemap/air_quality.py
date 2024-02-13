"""Support for openSenseMap Air Quality data."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.air_quality import PLATFORM_SCHEMA, AirQualityEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_STATION_ID, DOMAIN, MANUFACTURER
from .osm_data import OpenSenseMapData

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

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2024.1.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "openSenseMap",
        },
    )

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

    osm_api = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            OpenSenseMapQuality(
                name=entry.data[CONF_NAME],
                station_id=entry.data[CONF_STATION_ID],
                osm=osm_api,
            )
        ],
    )


class OpenSenseMapQuality(AirQualityEntity):
    """Implementation of an openSenseMap air quality entity."""

    _attr_attribution = "Data provided by openSenseMap"
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, name: str, station_id: str, osm: OpenSenseMapData) -> None:
        """Initialize the air quality entity."""
        self._name = name
        self._osm = osm
        self._attr_unique_id = f"{station_id}_sensor"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, station_id)},
            manufacturer=MANUFACTURER,
            name=name,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def particulate_matter_2_5(self) -> float:
        """Return the particulate matter 2.5 level."""
        return self._osm.api.pm2_5

    @property
    def particulate_matter_10(self) -> float:
        """Return the particulate matter 10 level."""
        return self._osm.api.pm10

    async def async_update(self) -> None:
        """Get the latest data from the openSenseMap API."""
        await self._osm.async_update()
