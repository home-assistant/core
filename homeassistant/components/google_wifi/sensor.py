"""Support for retrieving status info from Google Wifi/OnHub routers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_CURRENT_VERSION,
    ATTR_GROUP_ROLE,
    ATTR_LAST_RESTART,
    ATTR_LOCAL_IP,
    ATTR_MODEL,
    ATTR_NEW_VERSION,
    ATTR_STATUS,
    ATTR_UPTIME,
    DOMAIN,
)
from .coordinator import GoogleWifiUpdateCoordinator

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
    # Retrieve the data we stored in __init__.py
    data = hass.data[DOMAIN][entry.entry_id]
    ip_address = data["ip_address"]
    device_name = data["name"]

    # Create the coordinator to manage data updates
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Fetch initial data so we don't have empty sensors on startup
    await coordinator.async_config_entry_first_refresh()

    # Add all sensors defined in SENSOR_TYPES
    async_add_entities(
        GoogleWifiSensor(coordinator, description, device_name)
        for description in SENSOR_TYPES
    )


class GoogleWifiSensor(CoordinatorEntity[GoogleWifiUpdateCoordinator], SensorEntity):
    """Representation of a Google Wifi sensor."""

    entity_description: GoogleWifiSensorEntityDescription

    def __init__(
        self, coordinator: GoogleWifiUpdateCoordinator, description, device_name
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self.device_name = device_name
        # Create a unique ID so the user can rename/customize this in the UI
        self._attr_unique_id = f"{self.config_entry.entry_id}_{description.key}"
        self._attr_name = f"{description.key.replace('_', ' ').title()}"


    @property
    def device_info(self) -> DeviceInfo:
        """Attach sensors to a device in HomeAssistant."""
        # Pull the version and model name from the coordinator's data cache
        version = None
        model_name = "Onhub/Wifi"

        if self.coordinator.data:
            try:
                version = self.coordinator.data["software"]["softwareVersion"]
                model_name = self.coordinator.data["system"]["modelId"]
            except KeyError:
                version = None
                model_name = "Onhub/Wifi"

        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=self.device_name,
            manufacturer="Google",
            model=model_name,
            sw_version=version,
            configuration_url=f"http://{self.coordinator.host}/api/v1/status",
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor based on the coordinator data."""
        if not self.coordinator.data:
            return None

        raw_data = self.coordinator.data
        desc = self.entity_description

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

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
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
        breaks_in_ha_version="2026.9.0", # Set a future target version
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
        primary_key="software",
        sensor_key="softwareVersion",
        icon="mdi:checkbox-marked-circle-outline",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_NEW_VERSION,
        primary_key="software",
        sensor_key="updateNewVersion",
        icon="mdi:update",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_UPTIME,
        primary_key="system",
        sensor_key="uptime",
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:timelapse",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LAST_RESTART,
        primary_key="system",
        sensor_key="uptime",
        icon="mdi:restart",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LOCAL_IP,
        primary_key="wan",
        sensor_key="localIpAddress",
        icon="mdi:access-point-network",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_STATUS,
        primary_key="wan",
        sensor_key="online",
        icon="mdi:google",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_MODEL,
        primary_key="system",
        sensor_key="modelId",
        icon="mdi:router-network-wireless",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_GROUP_ROLE,
        primary_key="system",
        sensor_key="groupRole",
        icon="mdi:family-tree",
    ),
)
