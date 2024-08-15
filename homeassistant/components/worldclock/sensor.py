"""Support for showing the time in a different time zone."""

from __future__ import annotations

from datetime import tzinfo

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, CONF_TIME_ZONE
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import CONF_TIME_FORMAT, DEFAULT_NAME, DEFAULT_TIME_STR_FORMAT, DOMAIN

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TIME_ZONE): cv.time_zone,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TIME_FORMAT, default=DEFAULT_TIME_STR_FORMAT): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the World clock sensor."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2025.2.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Worldclock",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the World clock sensor entry."""
    time_zone = await dt_util.async_get_time_zone(entry.options[CONF_TIME_ZONE])
    async_add_entities(
        [
            WorldClockSensor(
                time_zone,
                entry.options[CONF_NAME],
                entry.options[CONF_TIME_FORMAT],
                entry.entry_id,
            )
        ],
        True,
    )


class WorldClockSensor(SensorEntity):
    """Representation of a World clock sensor."""

    _attr_icon = "mdi:clock"
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, time_zone: tzinfo | None, name: str, time_format: str, unique_id: str
    ) -> None:
        """Initialize the sensor."""
        self._time_zone = time_zone
        self._time_format = time_format
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=name,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Worldclock",
        )

    async def async_update(self) -> None:
        """Get the time and updates the states."""
        self._attr_native_value = dt_util.now(time_zone=self._time_zone).strftime(
            self._time_format
        )
