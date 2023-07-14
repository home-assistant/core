"""Sensor platform for Brottsplatskartan information."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from brottsplatskartan import ATTRIBUTION, BrottsplatsKartan
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import AREAS, CONF_APP_ID, CONF_AREA, DEFAULT_NAME, DOMAIN, LOGGER

SCAN_INTERVAL = timedelta(minutes=30)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_AREA, default=[]): vol.All(cv.ensure_list, [vol.In(AREAS)]),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Brottsplatskartan platform."""

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2023.11.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Brottsplatskartan",
        },
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Brottsplatskartan sensor entry."""

    area = entry.data.get(CONF_AREA)
    latitude = entry.data.get(CONF_LATITUDE)
    longitude = entry.data.get(CONF_LONGITUDE)
    app = entry.data[CONF_APP_ID]
    name = entry.title

    bpk = BrottsplatsKartan(app=app, area=area, latitude=latitude, longitude=longitude)

    async_add_entities([BrottsplatskartanSensor(bpk, name, entry.entry_id)], True)


class BrottsplatskartanSensor(SensorEntity):
    """Representation of a Brottsplatskartan Sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, bpk: BrottsplatsKartan, name: str, entry_id: str) -> None:
        """Initialize the Brottsplatskartan sensor."""
        self._brottsplatskartan = bpk
        self._attr_unique_id = entry_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Brottsplatskartan",
            name=name,
        )

    def update(self) -> None:
        """Update device state."""

        incident_counts: defaultdict[str, int] = defaultdict(int)
        incidents = self._brottsplatskartan.get_incidents()

        if incidents is False:
            LOGGER.debug("Problems fetching incidents")
            return

        for incident in incidents:
            if (incident_type := incident.get("title_type")) is not None:
                incident_counts[incident_type] += 1

        self._attr_extra_state_attributes = incident_counts
        self._attr_native_value = len(incidents)
