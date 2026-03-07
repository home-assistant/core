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
    # Add all sensors defined in SENSOR_TYPES
    async_add_entities(
        GoogleWifiSensor(entry, description) for description in SENSOR_TYPES
    )

    # Create the sensor objects
    entities = [GoogleWifiSensor(entry, description) for description in SENSOR_TYPES]

    # Trigger an initial update for all sensors immediately
    # so they have data before they are added to HA
    for entity in entities:
        await entity.async_update()

    async_add_entities(entities)

class GoogleWifiSensor(SensorEntity):
    """Representation of a Google Wifi sensor."""

    # Makes sensors get prefixed from device name
    _attr_has_entity_name = True
    # Type annotation
    _attr_data: dict[str, Any]

    def __init__(
        self, entry: ConfigEntry, description: GoogleWifiSensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._entry = entry
        self._attr_data = {}
        # Create a unique ID so the user can rename/customize this in the UI
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        # Use the name defined in the config entry title for the device name
        self._attr_name = cast(str | None, description.name)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information the router."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="Google",
            model=self._attr_data.get("system", {}).get("modelId", "Google Wifi"),
            # Use the current IP from the entry data for the link
            configuration_url=f"http://{self._entry.data[CONF_IP_ADDRESS]}/api/v1/status",
            # Pull software version from the last successful data fetch
            sw_version=self._attr_data.get("software", {}).get("softwareVersion"),
        )

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        host = self._entry.data[CONF_IP_ADDRESS]
        url = f"http://{host}/api/v1/status"

        try:
            # short timeout to prevent hanging the event loop
            # also if your own router isn't returning you data within 2 seconds... you aren't getting it.
            response = await self.hass.async_add_executor_job(
                lambda: requests.get(url, timeout=2)
            )
            response.raise_for_status()
            new_data = response.json()

            # Only update if we actually got data to prevent "Unknown" flickers
            if new_data:
                self._attr_data = new_data
                #mark as available to wipe any previous failure
                self._attr_available = True
        except Exception as err:
            _LOGGER.error("Error updating %s: %s", self.name, err)
            #mark as unavailable in case the router stonewalls us
            self._attr_available = False

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self._attr_data:
            return None

        # cast Desc as a googlewifisensorentitydescription so mypy stops being mad
        desc = cast(GoogleWifiSensorEntityDescription, self.entity_description)
        raw_data = self._attr_data

        try:
            val = raw_data[desc.primary_key][desc.sensor_key]
        except KeyError:
            return None
        else:
            # Formatting Logic
            if desc.key == ATTR_NEW_VERSION and val == "0.0.0.0":
                return "Latest"
            if desc.key == ATTR_UPTIME:
                return round(val / (3600 * 24), 2)
            if desc.key == ATTR_LAST_RESTART:
                last_restart = dt_util.now() - timedelta(seconds=val)
                return last_restart.strftime("%Y-%m-%d %H:%M:%S")
            if desc.key == ATTR_STATUS:
                return "Online" if val else "Offline"
            if desc.key == ATTR_LOCAL_IP and not raw_data["wan"]["online"]:
                return None

            return val


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
