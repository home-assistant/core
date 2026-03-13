"""Support for retrieving status info from Google Wifi/OnHub routers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, cast

import requests

from homeassistant import config_entries
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_CURRENT_VERSION,
    ATTR_LAST_RESTART,
    ATTR_LOCAL_IP,
    ATTR_NEW_VERSION,
    ATTR_STATUS,
    ATTR_UPTIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Define all sensors in one tuple to be imported by sensor.py
SENSOR_TYPES: tuple[GoogleWifiSensorEntityDescription, ...] = (
    GoogleWifiSensorEntityDescription(
        key=ATTR_CURRENT_VERSION,
        name="Software Version",
        primary_key="software",
        sensor_key="softwareVersion",
        icon="mdi:checkbox-marked-circle-outline",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_NEW_VERSION,
        name="New Version",
        primary_key="software",
        sensor_key="updateNewVersion",
        icon="mdi:update",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_UPTIME,
        name="Uptime",
        primary_key="system",
        sensor_key="uptime",
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:timelapse",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LAST_RESTART,
        name="Last Restart",
        primary_key="system",
        sensor_key="uptime",
        icon="mdi:restart",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LOCAL_IP,
        name="Local IP",
        primary_key="wan",
        sensor_key="localIpAddress",
        icon="mdi:access-point-network",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_STATUS,
        name="Status",
        primary_key="wan",
        sensor_key="online",
        icon="mdi:google",
    ),
)


@dataclass(frozen=True, kw_only=True)
class GoogleWifiSensorEntityDescription(SensorEntityDescription):
    """Describes Google Wifi sensor entity."""

    primary_key: str
    sensor_key: str

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Google Wifi sensor from a config entry."""
    # Get the shared API instance
    api = hass.data[DOMAIN][entry.entry_id]
    
    entities = [GoogleWifiSensor(api, entry, description) for description in SENSOR_TYPES]
    async_add_entities(entities)

class GoogleWifiSensor(SensorEntity):
    """Representation of a Google Wifi sensor."""

    _attr_has_entity_name = True

    def __init__(self, api, entry, description):
        """Initialize the sensor."""
        self.api = api
        self._entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return availability from API."""
        return self.api.available

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        # Pull software version from the API's formatted data
        from .const import ATTR_CURRENT_VERSION
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="Google",
            sw_version=self.api.data.get(ATTR_CURRENT_VERSION),
        )

    async def async_update(self) -> None:
        """Fetch new state data via the API class."""
        # Use executor because API.update is synchronous
        await self.hass.async_add_executor_job(self.api.update)

    @property
    def native_value(self):
        """Return the pre-formatted state from the API object."""
        # The API class already did the formatting in data_format()
        return self.api.data.get(self.entity_description.key)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Handle legacy YAML configuration by importing it."""

    # 1. Map legacy keys to modern ones
    # Old YAML might use 'host' while our flow uses 'ip_address'
    import_data = {
        CONF_IP_ADDRESS: config.get("host") or config.get(CONF_IP_ADDRESS),
        CONF_NAME: config.get(CONF_NAME, "Google Wifi"),
    }

    # 2. Filter out None values (ensure we have at least an IP)
    if not import_data[CONF_IP_ADDRESS]:
        _LOGGER.error("Legacy Google Wifi YAML missing 'host' or 'ip_address'")
        return

    # 3. Create a Repair Issue to warn the user that YAML is deprecated
    ir.async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2026.9.0",  # Arbitrary future target version to tell user this support is going away
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )

    # 4. Trigger the Config Flow import
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=import_data,
        )
    )
