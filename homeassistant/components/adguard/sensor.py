"""Support for AdGuard Home sensors."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from adguardhome import AdGuardHome, AdGuardHomeConnectionError

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_ADGUARD_CLIENT, DATA_ADGUARD_VERSION, DOMAIN
from .entity import AdGuardHomeEntity

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4


@dataclass(frozen=True, kw_only=True)
class AdGuardHomeEntityDescription(SensorEntityDescription):
    """Describes AdGuard Home sensor entity."""

    value_fn: Callable[[AdGuardHome], Coroutine[Any, Any, int | float]]


SENSORS: tuple[AdGuardHomeEntityDescription, ...] = (
    AdGuardHomeEntityDescription(
        key="dns_queries",
        translation_key="dns_queries",
        native_unit_of_measurement="queries",
        value_fn=lambda adguard: adguard.stats.dns_queries(),
    ),
    AdGuardHomeEntityDescription(
        key="blocked_filtering",
        translation_key="dns_queries_blocked",
        native_unit_of_measurement="queries",
        value_fn=lambda adguard: adguard.stats.blocked_filtering(),
    ),
    AdGuardHomeEntityDescription(
        key="blocked_percentage",
        translation_key="dns_queries_blocked_ratio",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda adguard: adguard.stats.blocked_percentage(),
    ),
    AdGuardHomeEntityDescription(
        key="blocked_parental",
        translation_key="parental_control_blocked",
        native_unit_of_measurement="requests",
        value_fn=lambda adguard: adguard.stats.replaced_parental(),
    ),
    AdGuardHomeEntityDescription(
        key="blocked_safebrowsing",
        translation_key="safe_browsing_blocked",
        native_unit_of_measurement="requests",
        value_fn=lambda adguard: adguard.stats.replaced_safebrowsing(),
    ),
    AdGuardHomeEntityDescription(
        key="enforced_safesearch",
        translation_key="safe_searches_enforced",
        native_unit_of_measurement="requests",
        value_fn=lambda adguard: adguard.stats.replaced_safesearch(),
    ),
    AdGuardHomeEntityDescription(
        key="average_speed",
        translation_key="average_processing_speed",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        value_fn=lambda adguard: adguard.stats.avg_processing_time(),
    ),
    AdGuardHomeEntityDescription(
        key="rules_count",
        translation_key="rules_count",
        native_unit_of_measurement="rules",
        value_fn=lambda adguard: adguard.filtering.rules_count(allowlist=False),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdGuard Home sensor based on a config entry."""
    adguard = hass.data[DOMAIN][entry.entry_id][DATA_ADGUARD_CLIENT]

    try:
        version = await adguard.version()
    except AdGuardHomeConnectionError as exception:
        raise PlatformNotReady from exception

    hass.data[DOMAIN][entry.entry_id][DATA_ADGUARD_VERSION] = version

    async_add_entities(
        [AdGuardHomeSensor(adguard, entry, description) for description in SENSORS],
        True,
    )


class AdGuardHomeSensor(AdGuardHomeEntity, SensorEntity):
    """Defines a AdGuard Home sensor."""

    entity_description: AdGuardHomeEntityDescription

    def __init__(
        self,
        adguard: AdGuardHome,
        entry: ConfigEntry,
        description: AdGuardHomeEntityDescription,
    ) -> None:
        """Initialize AdGuard Home sensor."""
        super().__init__(adguard, entry)
        self.entity_description = description
        self._attr_unique_id = "_".join(
            [
                DOMAIN,
                adguard.host,
                str(adguard.port),
                "sensor",
                description.key,
            ]
        )

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        value = await self.entity_description.value_fn(self.adguard)
        self._attr_native_value = value
        if isinstance(value, float):
            self._attr_native_value = f"{value:.2f}"
