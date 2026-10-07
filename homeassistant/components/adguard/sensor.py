"""Support for AdGuard Home sensors."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, override

from adguardhome import AdGuardHome, Stats

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import CONF_HOST, CONF_PORT, PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AdGuardConfigEntry, AdGuardData
from .const import DOMAIN
from .entity import AdGuardHomeEntity

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4


@dataclass(frozen=True, kw_only=True)
class AdGuardHomeEntityDescription(SensorEntityDescription):
    """Describes AdGuard Home sensor entity."""

    value_fn: Callable[[AdGuardHome], Coroutine[Any, Any, int | float]]


async def _stat(
    adguard: AdGuardHome, value: Callable[[Stats], int | float]
) -> int | float:
    """Return a value from the statistics of AdGuard Home."""
    return value(await adguard.stats.get())


async def _rules_count(adguard: AdGuardHome) -> int:
    """Return the number of rules in the blocklists of AdGuard Home."""
    return sum(
        blocklist.rules_count for blocklist in await adguard.filtering.blocklists.list()
    )


SENSORS: tuple[AdGuardHomeEntityDescription, ...] = (
    AdGuardHomeEntityDescription(
        key="dns_queries",
        translation_key="dns_queries",
        native_unit_of_measurement="queries",
        value_fn=lambda adguard: _stat(adguard, lambda stats: stats.dns_queries),
    ),
    AdGuardHomeEntityDescription(
        key="blocked_filtering",
        translation_key="dns_queries_blocked",
        native_unit_of_measurement="queries",
        value_fn=lambda adguard: _stat(adguard, lambda stats: stats.blocked_filtering),
    ),
    AdGuardHomeEntityDescription(
        key="blocked_percentage",
        translation_key="dns_queries_blocked_ratio",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda adguard: _stat(adguard, lambda stats: stats.blocked_percentage),
    ),
    AdGuardHomeEntityDescription(
        key="blocked_parental",
        translation_key="parental_control_blocked",
        native_unit_of_measurement="requests",
        value_fn=lambda adguard: _stat(adguard, lambda stats: stats.blocked_parental),
    ),
    AdGuardHomeEntityDescription(
        key="blocked_safebrowsing",
        translation_key="safe_browsing_blocked",
        native_unit_of_measurement="requests",
        value_fn=lambda adguard: _stat(
            adguard, lambda stats: stats.blocked_safebrowsing
        ),
    ),
    AdGuardHomeEntityDescription(
        key="enforced_safesearch",
        translation_key="safe_searches_enforced",
        native_unit_of_measurement="requests",
        value_fn=lambda adguard: _stat(
            adguard, lambda stats: stats.enforced_safesearch
        ),
    ),
    AdGuardHomeEntityDescription(
        key="average_speed",
        translation_key="average_processing_speed",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        value_fn=lambda adguard: _stat(
            adguard,
            lambda stats: stats.avg_processing_time / timedelta(milliseconds=1),
        ),
    ),
    AdGuardHomeEntityDescription(
        key="rules_count",
        translation_key="rules_count",
        native_unit_of_measurement="rules",
        value_fn=_rules_count,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdGuardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AdGuard Home sensor based on a config entry."""
    data = entry.runtime_data

    async_add_entities(
        [AdGuardHomeSensor(data, entry, description) for description in SENSORS],
        True,
    )


class AdGuardHomeSensor(AdGuardHomeEntity, SensorEntity):
    """Defines a AdGuard Home sensor."""

    entity_description: AdGuardHomeEntityDescription

    def __init__(
        self,
        data: AdGuardData,
        entry: AdGuardConfigEntry,
        description: AdGuardHomeEntityDescription,
    ) -> None:
        """Initialize AdGuard Home sensor."""
        super().__init__(data, entry)
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

    @override
    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        value = await self.entity_description.value_fn(self.adguard)
        self._attr_native_value = value
        if isinstance(value, float):
            self._attr_native_value = f"{value:.2f}"
