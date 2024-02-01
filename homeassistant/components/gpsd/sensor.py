"""Support for GPSD."""
from __future__ import annotations

import logging
from typing import Any

from gps3.agps3threaded import (
    GPSD_PORT as DEFAULT_PORT,
    HOST as DEFAULT_HOST,
    AGPS3mechanism,
)
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_MODE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_CLIMB = "climb"
ATTR_ELEVATION = "elevation"
ATTR_GPS_TIME = "gps_time"
ATTR_SPEED = "speed"

DEFAULT_NAME = "GPS"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the GPSD component."""
    async_add_entities(
        [
            GpsdSensor(
                config_entry.data[CONF_HOST],
                config_entry.data[CONF_PORT],
                config_entry.entry_id,
            )
        ]
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Initialize gpsd import from config."""
    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        is_fixable=False,
        breaks_in_ha_version="2024.9.0",
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "GPSD",
        },
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


class GpsdSensor(SensorEntity):
    """Representation of a GPS receiver available via GPSD."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "mode"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["2d_fix", "3d_fix"]

    def __init__(
        self,
        host: str,
        port: int,
        unique_id: str,
    ) -> None:
        """Initialize the GPSD sensor."""
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_unique_id = f"{unique_id}-mode"

        self.agps_thread = AGPS3mechanism()
        self.agps_thread.stream_data(host=host, port=port)
        self.agps_thread.run_thread()

    @property
    def native_value(self) -> str | None:
        """Return the state of GPSD."""
        if self.agps_thread.data_stream.mode == 3:
            return "3d_fix"
        if self.agps_thread.data_stream.mode == 2:
            return "2d_fix"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the GPS."""
        return {
            ATTR_LATITUDE: self.agps_thread.data_stream.lat,
            ATTR_LONGITUDE: self.agps_thread.data_stream.lon,
            ATTR_ELEVATION: self.agps_thread.data_stream.alt,
            ATTR_GPS_TIME: self.agps_thread.data_stream.time,
            ATTR_SPEED: self.agps_thread.data_stream.speed,
            ATTR_CLIMB: self.agps_thread.data_stream.climb,
            ATTR_MODE: self.agps_thread.data_stream.mode,
        }

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        mode = self.agps_thread.data_stream.mode

        if isinstance(mode, int) and mode >= 2:
            return "mdi:crosshairs-gps"
        return "mdi:crosshairs"
