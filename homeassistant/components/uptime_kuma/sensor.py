"""Sensor platform for the Uptime Kuma integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from pythonkuma import MonitorType, UptimeKumaMonitor
from pythonkuma.models import MonitorStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_URL, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, HAS_CERT, HAS_HOST, HAS_PORT, HAS_URL
from .coordinator import UptimeKumaConfigEntry, UptimeKumaDataUpdateCoordinator

PARALLEL_UPDATES = 0


class UptimeKumaSensor(StrEnum):
    """Uptime Kuma sensors."""

    CERT_DAYS_REMAINING = "cert_days_remaining"
    RESPONSE_TIME = "response_time"
    STATUS = "status"
    TYPE = "type"
    URL = "url"
    HOSTNAME = "hostname"
    PORT = "port"


@dataclass(kw_only=True, frozen=True)
class UptimeKumaSensorEntityDescription(SensorEntityDescription):
    """Uptime Kuma sensor description."""

    value_fn: Callable[[UptimeKumaMonitor], StateType]
    create_entity: Callable[[MonitorType], bool]


SENSOR_DESCRIPTIONS: tuple[UptimeKumaSensorEntityDescription, ...] = (
    UptimeKumaSensorEntityDescription(
        key=UptimeKumaSensor.CERT_DAYS_REMAINING,
        translation_key=UptimeKumaSensor.CERT_DAYS_REMAINING,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda m: m.monitor_cert_days_remaining,
        create_entity=lambda t: t in HAS_CERT,
    ),
    UptimeKumaSensorEntityDescription(
        key=UptimeKumaSensor.RESPONSE_TIME,
        translation_key=UptimeKumaSensor.RESPONSE_TIME,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        value_fn=(
            lambda m: m.monitor_response_time if m.monitor_response_time > -1 else None
        ),
        create_entity=lambda _: True,
    ),
    UptimeKumaSensorEntityDescription(
        key=UptimeKumaSensor.STATUS,
        translation_key=UptimeKumaSensor.STATUS,
        device_class=SensorDeviceClass.ENUM,
        options=[m.name.lower() for m in MonitorStatus],
        value_fn=lambda m: m.monitor_status.name.lower(),
        create_entity=lambda _: True,
    ),
    UptimeKumaSensorEntityDescription(
        key=UptimeKumaSensor.TYPE,
        translation_key=UptimeKumaSensor.TYPE,
        device_class=SensorDeviceClass.ENUM,
        options=[m.name.lower() for m in MonitorType],
        value_fn=lambda m: m.monitor_type.name.lower(),
        entity_category=EntityCategory.DIAGNOSTIC,
        create_entity=lambda _: True,
    ),
    UptimeKumaSensorEntityDescription(
        key=UptimeKumaSensor.URL,
        translation_key=UptimeKumaSensor.URL,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: m.monitor_url,
        create_entity=lambda t: t in HAS_URL,
    ),
    UptimeKumaSensorEntityDescription(
        key=UptimeKumaSensor.HOSTNAME,
        translation_key=UptimeKumaSensor.HOSTNAME,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: m.monitor_hostname,
        create_entity=lambda t: t in HAS_HOST,
    ),
    UptimeKumaSensorEntityDescription(
        key=UptimeKumaSensor.PORT,
        translation_key=UptimeKumaSensor.PORT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: m.monitor_port,
        create_entity=lambda t: t in HAS_PORT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UptimeKumaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data
    monitor_added: set[str | int] = set()

    @callback
    def add_entities() -> None:
        """Add sensor entities."""
        nonlocal monitor_added

        if new_monitor := set(coordinator.data.keys()) - monitor_added:
            async_add_entities(
                UptimeKumaSensorEntity(coordinator, monitor, description)
                for description in SENSOR_DESCRIPTIONS
                for monitor in new_monitor
                if description.create_entity(coordinator.data[monitor].monitor_type)
            )
            monitor_added |= new_monitor

    coordinator.async_add_listener(add_entities)
    add_entities()


class UptimeKumaSensorEntity(
    CoordinatorEntity[UptimeKumaDataUpdateCoordinator], SensorEntity
):
    """An Uptime Kuma sensor entity."""

    entity_description: UptimeKumaSensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UptimeKumaDataUpdateCoordinator,
        monitor: str | int,
        entity_description: UptimeKumaSensorEntityDescription,
    ) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)
        self.monitor = monitor
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{monitor!s}_{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            name=coordinator.data[monitor].monitor_name,
            identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_{monitor!s}")},
            manufacturer="Uptime Kuma",
            configuration_url=(
                None
                if "127.0.0.1" in (url := coordinator.config_entry.data[CONF_URL])
                else url
            ),
            sw_version=coordinator.api.version.version,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""

        return self.entity_description.value_fn(self.coordinator.data[self.monitor])

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.monitor in self.coordinator.data
