"""Support for Netgear LTE sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from eternalegypt.eternalegypt import Information

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import NetgearLTEConfigEntry
from .entity import LTEEntity


@dataclass(frozen=True, kw_only=True)
class NetgearLTESensorEntityDescription(SensorEntityDescription):
    """Class describing Netgear LTE entities."""

    value_fn: Callable[[Information], StateType] | None = None


SENSORS: tuple[NetgearLTESensorEntityDescription, ...] = (
    NetgearLTESensorEntityDescription(
        key="sms",
        translation_key="sms",
        native_unit_of_measurement="unread",
        value_fn=lambda data: sum(1 for x in data.sms if x.unread),
    ),
    NetgearLTESensorEntityDescription(
        key="sms_total",
        translation_key="sms_total",
        native_unit_of_measurement="messages",
        value_fn=lambda data: len(data.sms),
    ),
    NetgearLTESensorEntityDescription(
        key="usage",
        translation_key="usage",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        suggested_display_precision=1,
        value_fn=lambda data: data.usage,
    ),
    NetgearLTESensorEntityDescription(
        key="radio_quality",
        translation_key="radio_quality",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
    ),
    NetgearLTESensorEntityDescription(
        key="rx_level",
        translation_key="rx_level",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ),
    NetgearLTESensorEntityDescription(
        key="tx_level",
        translation_key="tx_level",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ),
    NetgearLTESensorEntityDescription(
        key="upstream",
        translation_key="upstream",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NetgearLTESensorEntityDescription(
        key="connection_text",
        translation_key="connection_text",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NetgearLTESensorEntityDescription(
        key="connection_type",
        translation_key="connection_type",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NetgearLTESensorEntityDescription(
        key="current_ps_service_type",
        translation_key="service_type",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NetgearLTESensorEntityDescription(
        key="register_network_display",
        translation_key="register_network_display",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NetgearLTESensorEntityDescription(
        key="current_band",
        translation_key="band",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NetgearLTESensorEntityDescription(
        key="cell_id",
        translation_key="cell_id",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetgearLTEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Netgear LTE sensor."""
    async_add_entities(NetgearLTESensor(entry, description) for description in SENSORS)


class NetgearLTESensor(LTEEntity, SensorEntity):
    """Base LTE sensor entity."""

    entity_description: NetgearLTESensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(self.coordinator.data)
        return getattr(self.coordinator.data, self.entity_description.key)
