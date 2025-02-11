"""Support for the NextDNS service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic

from nextdns import (
    AnalyticsDnssec,
    AnalyticsEncryption,
    AnalyticsIpVersions,
    AnalyticsProtocols,
    AnalyticsStatus,
)

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NextDnsConfigEntry
from .const import (
    ATTR_DNSSEC,
    ATTR_ENCRYPTION,
    ATTR_IP_VERSIONS,
    ATTR_PROTOCOLS,
    ATTR_STATUS,
)
from .coordinator import CoordinatorDataT, NextDnsUpdateCoordinator

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class NextDnsSensorEntityDescription(
    SensorEntityDescription, Generic[CoordinatorDataT]
):
    """NextDNS sensor entity description."""

    coordinator_type: str
    value: Callable[[CoordinatorDataT], StateType]


SENSORS: tuple[NextDnsSensorEntityDescription, ...] = (
    NextDnsSensorEntityDescription[AnalyticsStatus](
        key="all_queries",
        coordinator_type=ATTR_STATUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="all_queries",
        state_class=SensorStateClass.TOTAL,
        value=lambda data: data.all_queries,
    ),
    NextDnsSensorEntityDescription[AnalyticsStatus](
        key="blocked_queries",
        coordinator_type=ATTR_STATUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="blocked_queries",
        state_class=SensorStateClass.TOTAL,
        value=lambda data: data.blocked_queries,
    ),
    NextDnsSensorEntityDescription[AnalyticsStatus](
        key="relayed_queries",
        coordinator_type=ATTR_STATUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="relayed_queries",
        state_class=SensorStateClass.TOTAL,
        value=lambda data: data.relayed_queries,
    ),
    NextDnsSensorEntityDescription[AnalyticsStatus](
        key="blocked_queries_ratio",
        coordinator_type=ATTR_STATUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="blocked_queries_ratio",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.blocked_queries_ratio,
    ),
    NextDnsSensorEntityDescription[AnalyticsProtocols](
        key="doh_queries",
        coordinator_type=ATTR_PROTOCOLS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="doh_queries",
        state_class=SensorStateClass.TOTAL,
        value=lambda data: data.doh_queries,
    ),
    NextDnsSensorEntityDescription[AnalyticsProtocols](
        key="doh3_queries",
        coordinator_type=ATTR_PROTOCOLS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="doh3_queries",
        state_class=SensorStateClass.TOTAL,
        value=lambda data: data.doh3_queries,
    ),
    NextDnsSensorEntityDescription[AnalyticsProtocols](
        key="dot_queries",
        coordinator_type=ATTR_PROTOCOLS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="dot_queries",
        state_class=SensorStateClass.TOTAL,
        value=lambda data: data.dot_queries,
    ),
    NextDnsSensorEntityDescription[AnalyticsProtocols](
        key="doq_queries",
        coordinator_type=ATTR_PROTOCOLS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="doq_queries",
        state_class=SensorStateClass.TOTAL,
        value=lambda data: data.doq_queries,
    ),
    NextDnsSensorEntityDescription[AnalyticsProtocols](
        key="tcp_queries",
        coordinator_type=ATTR_PROTOCOLS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="tcp_queries",
        state_class=SensorStateClass.TOTAL,
        value=lambda data: data.tcp_queries,
    ),
    NextDnsSensorEntityDescription[AnalyticsProtocols](
        key="udp_queries",
        coordinator_type=ATTR_PROTOCOLS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="udp_queries",
        state_class=SensorStateClass.TOTAL,
        value=lambda data: data.udp_queries,
    ),
    NextDnsSensorEntityDescription[AnalyticsProtocols](
        key="doh_queries_ratio",
        coordinator_type=ATTR_PROTOCOLS,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="doh_queries_ratio",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.doh_queries_ratio,
    ),
    NextDnsSensorEntityDescription[AnalyticsProtocols](
        key="doh3_queries_ratio",
        coordinator_type=ATTR_PROTOCOLS,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="doh3_queries_ratio",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.doh3_queries_ratio,
    ),
    NextDnsSensorEntityDescription[AnalyticsProtocols](
        key="dot_queries_ratio",
        coordinator_type=ATTR_PROTOCOLS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="dot_queries_ratio",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.dot_queries_ratio,
    ),
    NextDnsSensorEntityDescription[AnalyticsProtocols](
        key="doq_queries_ratio",
        coordinator_type=ATTR_PROTOCOLS,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="doq_queries_ratio",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.doq_queries_ratio,
    ),
    NextDnsSensorEntityDescription[AnalyticsProtocols](
        key="tcp_queries_ratio",
        coordinator_type=ATTR_PROTOCOLS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="tcp_queries_ratio",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.tcp_queries_ratio,
    ),
    NextDnsSensorEntityDescription[AnalyticsProtocols](
        key="udp_queries_ratio",
        coordinator_type=ATTR_PROTOCOLS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="udp_queries_ratio",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.udp_queries_ratio,
    ),
    NextDnsSensorEntityDescription[AnalyticsEncryption](
        key="encrypted_queries",
        coordinator_type=ATTR_ENCRYPTION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="encrypted_queries",
        state_class=SensorStateClass.TOTAL,
        value=lambda data: data.encrypted_queries,
    ),
    NextDnsSensorEntityDescription[AnalyticsEncryption](
        key="unencrypted_queries",
        coordinator_type=ATTR_ENCRYPTION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="unencrypted_queries",
        state_class=SensorStateClass.TOTAL,
        value=lambda data: data.unencrypted_queries,
    ),
    NextDnsSensorEntityDescription[AnalyticsEncryption](
        key="encrypted_queries_ratio",
        coordinator_type=ATTR_ENCRYPTION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="encrypted_queries_ratio",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.encrypted_queries_ratio,
    ),
    NextDnsSensorEntityDescription[AnalyticsIpVersions](
        key="ipv4_queries",
        coordinator_type=ATTR_IP_VERSIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="ipv4_queries",
        state_class=SensorStateClass.TOTAL,
        value=lambda data: data.ipv4_queries,
    ),
    NextDnsSensorEntityDescription[AnalyticsIpVersions](
        key="ipv6_queries",
        coordinator_type=ATTR_IP_VERSIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="ipv6_queries",
        state_class=SensorStateClass.TOTAL,
        value=lambda data: data.ipv6_queries,
    ),
    NextDnsSensorEntityDescription[AnalyticsIpVersions](
        key="ipv6_queries_ratio",
        coordinator_type=ATTR_IP_VERSIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="ipv6_queries_ratio",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.ipv6_queries_ratio,
    ),
    NextDnsSensorEntityDescription[AnalyticsDnssec](
        key="validated_queries",
        coordinator_type=ATTR_DNSSEC,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="validated_queries",
        state_class=SensorStateClass.TOTAL,
        value=lambda data: data.validated_queries,
    ),
    NextDnsSensorEntityDescription[AnalyticsDnssec](
        key="not_validated_queries",
        coordinator_type=ATTR_DNSSEC,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="not_validated_queries",
        state_class=SensorStateClass.TOTAL,
        value=lambda data: data.not_validated_queries,
    ),
    NextDnsSensorEntityDescription[AnalyticsDnssec](
        key="validated_queries_ratio",
        coordinator_type=ATTR_DNSSEC,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="validated_queries_ratio",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.validated_queries_ratio,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NextDnsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a NextDNS entities from a config_entry."""
    async_add_entities(
        NextDnsSensor(
            getattr(entry.runtime_data, description.coordinator_type), description
        )
        for description in SENSORS
    )


class NextDnsSensor(
    CoordinatorEntity[NextDnsUpdateCoordinator[CoordinatorDataT]], SensorEntity
):
    """Define an NextDNS sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NextDnsUpdateCoordinator[CoordinatorDataT],
        description: NextDnsSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.profile_id}_{description.key}"
        self._attr_native_value = description.value(coordinator.data)
        self.entity_description: NextDnsSensorEntityDescription = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.entity_description.value(self.coordinator.data)
        self.async_write_ha_state()
