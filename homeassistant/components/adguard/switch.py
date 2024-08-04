"""Support for AdGuard Home switches."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from adguardhome import AdGuardHome, AdGuardHomeError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AdGuardConfigEntry, AdGuardData
from .const import DOMAIN, LOGGER
from .entity import AdGuardHomeEntity

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AdGuardHomeSwitchEntityDescription(SwitchEntityDescription):
    """Describes AdGuard Home switch entity."""

    is_on_fn: Callable[[AdGuardHome], Callable[[], Coroutine[Any, Any, bool]]]
    turn_on_fn: Callable[[AdGuardHome], Callable[[], Coroutine[Any, Any, None]]]
    turn_off_fn: Callable[[AdGuardHome], Callable[[], Coroutine[Any, Any, None]]]


SWITCHES: tuple[AdGuardHomeSwitchEntityDescription, ...] = (
    AdGuardHomeSwitchEntityDescription(
        key="protection",
        translation_key="protection",
        is_on_fn=lambda adguard: adguard.protection_enabled,
        turn_on_fn=lambda adguard: adguard.enable_protection,
        turn_off_fn=lambda adguard: adguard.disable_protection,
    ),
    AdGuardHomeSwitchEntityDescription(
        key="parental",
        translation_key="parental",
        is_on_fn=lambda adguard: adguard.parental.enabled,
        turn_on_fn=lambda adguard: adguard.parental.enable,
        turn_off_fn=lambda adguard: adguard.parental.disable,
    ),
    AdGuardHomeSwitchEntityDescription(
        key="safesearch",
        translation_key="safe_search",
        is_on_fn=lambda adguard: adguard.safesearch.enabled,
        turn_on_fn=lambda adguard: adguard.safesearch.enable,
        turn_off_fn=lambda adguard: adguard.safesearch.disable,
    ),
    AdGuardHomeSwitchEntityDescription(
        key="safebrowsing",
        translation_key="safe_browsing",
        is_on_fn=lambda adguard: adguard.safebrowsing.enabled,
        turn_on_fn=lambda adguard: adguard.safebrowsing.enable,
        turn_off_fn=lambda adguard: adguard.safebrowsing.disable,
    ),
    AdGuardHomeSwitchEntityDescription(
        key="filtering",
        translation_key="filtering",
        is_on_fn=lambda adguard: adguard.filtering.enabled,
        turn_on_fn=lambda adguard: adguard.filtering.enable,
        turn_off_fn=lambda adguard: adguard.filtering.disable,
    ),
    AdGuardHomeSwitchEntityDescription(
        key="querylog",
        translation_key="query_log",
        is_on_fn=lambda adguard: adguard.querylog.enabled,
        turn_on_fn=lambda adguard: adguard.querylog.enable,
        turn_off_fn=lambda adguard: adguard.querylog.disable,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdGuardConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdGuard Home switch based on a config entry."""
    data = entry.runtime_data

    async_add_entities(
        [AdGuardHomeSwitch(data, entry, description) for description in SWITCHES],
        True,
    )


class AdGuardHomeSwitch(AdGuardHomeEntity, SwitchEntity):
    """Defines a AdGuard Home switch."""

    entity_description: AdGuardHomeSwitchEntityDescription

    def __init__(
        self,
        data: AdGuardData,
        entry: AdGuardConfigEntry,
        description: AdGuardHomeSwitchEntityDescription,
    ) -> None:
        """Initialize AdGuard Home switch."""
        super().__init__(data, entry)
        self.entity_description = description
        self._attr_unique_id = "_".join(
            [
                DOMAIN,
                self.adguard.host,
                str(self.adguard.port),
                "switch",
                description.key,
            ]
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        try:
            await self.entity_description.turn_off_fn(self.adguard)()
        except AdGuardHomeError:
            LOGGER.error("An error occurred while turning off AdGuard Home switch")
            self._attr_available = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        try:
            await self.entity_description.turn_on_fn(self.adguard)()
        except AdGuardHomeError:
            LOGGER.error("An error occurred while turning on AdGuard Home switch")
            self._attr_available = False

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        self._attr_is_on = await self.entity_description.is_on_fn(self.adguard)()
