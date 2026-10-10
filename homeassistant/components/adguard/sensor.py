"""Support for AdGuard Home sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_HOST, CONF_PORT, PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    AdGuardConfigEntry,
    AdGuardHomeStatistics,
    AdGuardHomeStatisticsCoordinator,
)
from .entity import AdGuardHomeEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AdGuardHomeEntityDescription(SensorEntityDescription):
    """Describes AdGuard Home sensor entity."""

    value_fn: Callable[[AdGuardHomeStatistics], int | float]


SENSORS: tuple[AdGuardHomeEntityDescription, ...] = (
    AdGuardHomeEntityDescription(
        key="dns_queries",
        translation_key="dns_queries",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="queries",
        value_fn=lambda data: data.stats.dns_queries,
    ),
    AdGuardHomeEntityDescription(
        key="blocked_filtering",
        translation_key="dns_queries_blocked",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="queries",
        value_fn=lambda data: data.stats.blocked_filtering,
    ),
    AdGuardHomeEntityDescription(
        key="blocked_percentage",
        translation_key="dns_queries_blocked_ratio",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
        value_fn=lambda data: data.stats.blocked_percentage,
    ),
    AdGuardHomeEntityDescription(
        key="blocked_parental",
        translation_key="parental_control_blocked",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="requests",
        value_fn=lambda data: data.stats.blocked_parental,
    ),
    AdGuardHomeEntityDescription(
        key="blocked_safebrowsing",
        translation_key="safe_browsing_blocked",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="requests",
        value_fn=lambda data: data.stats.blocked_safebrowsing,
    ),
    AdGuardHomeEntityDescription(
        key="enforced_safesearch",
        translation_key="safe_searches_enforced",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="requests",
        value_fn=lambda data: data.stats.enforced_safesearch,
    ),
    AdGuardHomeEntityDescription(
        key="average_speed",
        translation_key="average_processing_speed",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        suggested_display_precision=2,
        value_fn=lambda data: (
            data.stats.avg_processing_time / timedelta(milliseconds=1)
        ),
    ),
    AdGuardHomeEntityDescription(
        key="rules_count",
        translation_key="rules_count",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="rules",
        value_fn=lambda data: sum(
            blocklist.rules_count for blocklist in data.blocklists
        ),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdGuardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AdGuard Home sensor based on a config entry."""
    coordinator = entry.runtime_data.statistics

    async_add_entities(
        AdGuardHomeSensor(coordinator, description) for description in SENSORS
    )


class AdGuardHomeSensor(
    AdGuardHomeEntity[AdGuardHomeStatisticsCoordinator], SensorEntity
):
    """Defines a AdGuard Home sensor."""

    entity_description: AdGuardHomeEntityDescription

    def __init__(
        self,
        coordinator: AdGuardHomeStatisticsCoordinator,
        description: AdGuardHomeEntityDescription,
    ) -> None:
        """Initialize AdGuard Home sensor."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self.entity_description = description
        # Legacy format, kept as migrating existing unique IDs is not worth the risk
        self._attr_unique_id = "_".join(  # pylint: disable=home-assistant-entity-unique-id-redundant-domain,home-assistant-entity-unique-id-redundant-platform
            [
                DOMAIN,
                entry.data[CONF_HOST],
                str(entry.data[CONF_PORT]),
                "sensor",
                description.key,
            ]
        )

    @property
    @override
    def native_value(self) -> int | float:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
