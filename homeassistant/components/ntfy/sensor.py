"""Sensor platform for ntfy integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from aiontfy import Account as NtfyAccount
from yarl import URL

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_URL, EntityCategory, UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NtfyConfigEntry, NtfyDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class NtfySensorEntityDescription(SensorEntityDescription):
    """Ntfy Sensor Description."""

    value_fn: Callable[[NtfyAccount], StateType]


class NtfySensor(StrEnum):
    """Ntfy sensors."""

    MESSAGES = "messages"
    MESSAGES_REMAINING = "messages_remaining"
    MESSAGES_LIMIT = "messages_limit"
    MESSAGES_EXPIRY_DURATION = "messages_expiry_duration"
    EMAILS = "emails"
    EMAILS_REMAINING = "emails_remaining"
    EMAILS_LIMIT = "emails_limit"
    CALLS = "calls"
    CALLS_REMAINING = "calls_remaining"
    CALLS_LIMIT = "calls_limit"
    RESERVATIONS = "reservations"
    RESERVATIONS_REMAINING = "reservations_remaining"
    RESERVATIONS_LIMIT = "reservations_limit"
    ATTACHMENT_TOTAL_SIZE = "attachment_total_size"
    ATTACHMENT_TOTAL_SIZE_REMAINING = "attachment_total_size_remaining"
    ATTACHMENT_TOTAL_SIZE_LIMIT = "attachment_total_size_limit"
    ATTACHMENT_EXPIRY_DURATION = "attachment_expiry_duration"
    ATTACHMENT_BANDWIDTH = "attachment_bandwidth"
    ATTACHMENT_FILE_SIZE = "attachment_file_size"
    TIER = "tier"


SENSOR_DESCRIPTIONS: tuple[NtfySensorEntityDescription, ...] = (
    NtfySensorEntityDescription(
        key=NtfySensor.MESSAGES,
        translation_key=NtfySensor.MESSAGES,
        value_fn=lambda account: account.stats.messages,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.MESSAGES_REMAINING,
        translation_key=NtfySensor.MESSAGES_REMAINING,
        value_fn=lambda account: account.stats.messages_remaining,
        entity_registry_enabled_default=False,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.MESSAGES_LIMIT,
        translation_key=NtfySensor.MESSAGES_LIMIT,
        value_fn=lambda account: account.limits.messages if account.limits else None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.MESSAGES_EXPIRY_DURATION,
        translation_key=NtfySensor.MESSAGES_EXPIRY_DURATION,
        value_fn=(
            lambda account: account.limits.messages_expiry_duration
            if account.limits
            else None
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.EMAILS,
        translation_key=NtfySensor.EMAILS,
        value_fn=lambda account: account.stats.emails,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.EMAILS_REMAINING,
        translation_key=NtfySensor.EMAILS_REMAINING,
        value_fn=lambda account: account.stats.emails_remaining,
        entity_registry_enabled_default=False,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.EMAILS_LIMIT,
        translation_key=NtfySensor.EMAILS_LIMIT,
        value_fn=lambda account: account.limits.emails if account.limits else None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.CALLS,
        translation_key=NtfySensor.CALLS,
        value_fn=lambda account: account.stats.calls,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.CALLS_REMAINING,
        translation_key=NtfySensor.CALLS_REMAINING,
        value_fn=lambda account: account.stats.calls_remaining,
        entity_registry_enabled_default=False,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.CALLS_LIMIT,
        translation_key=NtfySensor.CALLS_LIMIT,
        value_fn=lambda account: account.limits.calls if account.limits else None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.RESERVATIONS,
        translation_key=NtfySensor.RESERVATIONS,
        value_fn=lambda account: account.stats.reservations,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.RESERVATIONS_REMAINING,
        translation_key=NtfySensor.RESERVATIONS_REMAINING,
        value_fn=lambda account: account.stats.reservations_remaining,
        entity_registry_enabled_default=False,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.RESERVATIONS_LIMIT,
        translation_key=NtfySensor.RESERVATIONS_LIMIT,
        value_fn=(
            lambda account: account.limits.reservations if account.limits else None
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.ATTACHMENT_EXPIRY_DURATION,
        translation_key=NtfySensor.ATTACHMENT_EXPIRY_DURATION,
        value_fn=(
            lambda account: account.limits.attachment_expiry_duration
            if account.limits
            else None
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.ATTACHMENT_TOTAL_SIZE,
        translation_key=NtfySensor.ATTACHMENT_TOTAL_SIZE,
        value_fn=lambda account: account.stats.attachment_total_size,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        suggested_display_precision=0,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.ATTACHMENT_TOTAL_SIZE_REMAINING,
        translation_key=NtfySensor.ATTACHMENT_TOTAL_SIZE_REMAINING,
        value_fn=lambda account: account.stats.attachment_total_size_remaining,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.ATTACHMENT_TOTAL_SIZE_LIMIT,
        translation_key=NtfySensor.ATTACHMENT_TOTAL_SIZE_LIMIT,
        value_fn=(
            lambda account: account.limits.attachment_total_size
            if account.limits
            else None
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        suggested_display_precision=0,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.ATTACHMENT_FILE_SIZE,
        translation_key=NtfySensor.ATTACHMENT_FILE_SIZE,
        value_fn=(
            lambda account: account.limits.attachment_file_size
            if account.limits
            else None
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        suggested_display_precision=0,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.ATTACHMENT_BANDWIDTH,
        translation_key=NtfySensor.ATTACHMENT_BANDWIDTH,
        value_fn=(
            lambda account: account.limits.attachment_bandwidth
            if account.limits
            else None
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        suggested_display_precision=0,
    ),
    NtfySensorEntityDescription(
        key=NtfySensor.TIER,
        translation_key=NtfySensor.TIER,
        value_fn=lambda account: account.tier.name if account.tier else "free",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NtfyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        NtfySensorEntity(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class NtfySensorEntity(CoordinatorEntity[NtfyDataUpdateCoordinator], SensorEntity):
    """Representation of a ntfy sensor entity."""

    entity_description: NtfySensorEntityDescription
    coordinator: NtfyDataUpdateCoordinator

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NtfyDataUpdateCoordinator,
        description: NtfySensorEntityDescription,
    ) -> None:
        """Initialize a sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="ntfy LLC",
            model="ntfy",
            configuration_url=URL(coordinator.config_entry.data[CONF_URL]) / "app",
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""

        return self.entity_description.value_fn(self.coordinator.data)
