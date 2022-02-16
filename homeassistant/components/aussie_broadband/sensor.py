"""Support for Aussie Broadband metric sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_KILOBYTES, DATA_MEGABYTES, TIME_DAYS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SERVICE_ID


@dataclass
class SensorValueEntityDescription(SensorEntityDescription):
    """Class describing Aussie Broadband sensor entities."""

    value: Callable = lambda x: x


SENSOR_DESCRIPTIONS: tuple[SensorValueEntityDescription, ...] = (
    # Internet Services sensors
    SensorValueEntityDescription(
        key="usedMb",
        name="Data Used",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:network",
    ),
    SensorValueEntityDescription(
        key="downloadedMb",
        name="Downloaded",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:download-network",
    ),
    SensorValueEntityDescription(
        key="uploadedMb",
        name="Uploaded",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:upload-network",
    ),
    # Mobile Phone Services sensors
    SensorValueEntityDescription(
        key="national",
        name="National Calls",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:phone",
        value=lambda x: x.get("calls"),
    ),
    SensorValueEntityDescription(
        key="mobile",
        name="Mobile Calls",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:phone",
        value=lambda x: x.get("calls"),
    ),
    SensorValueEntityDescription(
        key="international",
        name="International Calls",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:phone-plus",
    ),
    SensorValueEntityDescription(
        key="sms",
        name="SMS Sent",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:message-processing",
        value=lambda x: x.get("calls"),
    ),
    SensorValueEntityDescription(
        key="internet",
        name="Data Used",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=DATA_KILOBYTES,
        icon="mdi:network",
        value=lambda x: x.get("kbytes"),
    ),
    SensorValueEntityDescription(
        key="voicemail",
        name="Voicemail Calls",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:phone",
    ),
    SensorValueEntityDescription(
        key="other",
        name="Other Calls",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:phone",
    ),
    # Generic sensors
    SensorValueEntityDescription(
        key="daysTotal",
        name="Billing Cycle Length",
        native_unit_of_measurement=TIME_DAYS,
        icon="mdi:calendar-range",
    ),
    SensorValueEntityDescription(
        key="daysRemaining",
        name="Billing Cycle Remaining",
        native_unit_of_measurement=TIME_DAYS,
        icon="mdi:calendar-clock",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Aussie Broadband sensor platform from a config entry."""

    async_add_entities(
        [
            AussieBroadandSensorEntity(service, description)
            for service in hass.data[DOMAIN][entry.entry_id]["services"]
            for description in SENSOR_DESCRIPTIONS
            if description.key in service["coordinator"].data
        ]
    )


class AussieBroadandSensorEntity(CoordinatorEntity, SensorEntity):
    """Base class for Aussie Broadband metric sensors."""

    entity_description: SensorValueEntityDescription

    def __init__(
        self, service: dict[str, Any], description: SensorValueEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(service["coordinator"])
        self.entity_description = description
        self._attr_unique_id = f"{service[SERVICE_ID]}:{description.key}"
        self._attr_name = f"{service['name']} {description.name}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, service[SERVICE_ID])},
            manufacturer="Aussie Broadband",
            configuration_url=f"https://my.aussiebroadband.com.au/#/{service['name'].lower()}/{service[SERVICE_ID]}/",
            name=service["description"],
            model=service["name"],
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        parent = self.coordinator.data[self.entity_description.key]
        return cast(StateType, self.entity_description.value(parent))
