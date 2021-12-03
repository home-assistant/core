"""Support for Aussie Broadband metric sensors."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_KILOBYTES, DATA_MEGABYTES, TIME_DAYS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SERVICE_ID

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    # Internet Services sensors
    SensorEntityDescription(
        key="usedMb",
        name="Data Used",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:network",
    ),
    SensorEntityDescription(
        key="downloadedMb",
        name="Downloaded",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:download-network",
    ),
    SensorEntityDescription(
        key="uploadedMb",
        name="Uploaded",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:upload-network",
    ),
    # Mobile Phone Services sensors
    SensorEntityDescription(
        key="national",
        name="National Calls",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:phone",
    ),
    SensorEntityDescription(
        key="mobile",
        name="Mobile Calls",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:phone",
    ),
    SensorEntityDescription(
        key="international",
        name="International Calls",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:phone-plus",
    ),
    SensorEntityDescription(
        key="sms",
        name="SMS Sent",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:message-processing",
    ),
    SensorEntityDescription(
        key="internet",
        name="Data Used",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=DATA_KILOBYTES,
        icon="mdi:network",
    ),
    SensorEntityDescription(
        key="voicemail",
        name="Voicemail Calls",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:phone",
    ),
    SensorEntityDescription(
        key="other",
        name="Other Calls",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:phone",
    ),
    # Generic sensors
    SensorEntityDescription(
        key="daysTotal",
        name="Billing Cycle Length",
        native_unit_of_measurement=TIME_DAYS,
        icon="mdi:calendar-range",
    ),
    SensorEntityDescription(
        key="daysRemaining",
        name="Billing Cycle Remaining",
        native_unit_of_measurement=TIME_DAYS,
        icon="mdi:calendar-clock",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up the Aussie Broadband sensor platform from a config entry."""

    async_add_entities(
        [
            AussieBroadandSensorEntity(service, description)
            for service in hass.data[DOMAIN][entry.entry_id]["services"]
            for description in SENSOR_DESCRIPTIONS
            if description.key in service["coordinator"].data
        ]
    )
    return True


class AussieBroadandSensorEntity(CoordinatorEntity, SensorEntity):
    """Base class for Aussie Broadband metric sensors."""

    def __init__(
        self, service: dict[str, Any], description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(service["coordinator"])
        self.entity_description = description
        self._attr_unique_id = f"{service[SERVICE_ID]}:{description.key}"
        self._attr_name = f"{service['name']} {description.name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.entity_description.key == "internet":
            return self.coordinator.data[self.entity_description.key]["kbytes"]
        if self.entity_description.key in ("national", "mobile", "sms"):
            return self.coordinator.data[self.entity_description.key]["calls"]
        return self.coordinator.data[self.entity_description.key]
