"""Support for the NextDNS service."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, cast

from nextdns import Settings

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NextDnsSettingsUpdateCoordinator, TCoordinatorData
from .const import ATTR_SETTINGS, DOMAIN

PARALLEL_UPDATES = 1


@dataclass
class NextDnsSwitchRequiredKeysMixin(Generic[TCoordinatorData]):
    """Class for NextDNS entity required keys."""

    state: Callable[[TCoordinatorData], bool]


@dataclass
class NextDnsSwitchEntityDescription(
    SwitchEntityDescription, NextDnsSwitchRequiredKeysMixin[TCoordinatorData]
):
    """NextDNS switch entity description."""


SWITCHES = (
    NextDnsSwitchEntityDescription[Settings](
        key="block_page",
        name="{profile_name} Block Page",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:web-cancel",
        state=lambda data: data.block_page,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="cache_boost",
        name="{profile_name} Cache Boost",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:memory",
        state=lambda data: data.cache_boost,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="cname_flattening",
        name="{profile_name} CNAME Flattening",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:tournament",
        state=lambda data: data.cname_flattening,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="anonymized_ecs",
        name="{profile_name} Anonymized EDNS Client Subnet",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:incognito",
        state=lambda data: data.anonymized_ecs,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="logs",
        name="{profile_name} Logs",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:file-document-outline",
        state=lambda data: data.logs,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="web3",
        name="{profile_name} Web3",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:web",
        state=lambda data: data.web3,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="allow_affiliate",
        name="{profile_name} Allow Affiliate & Tracking Links",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.allow_affiliate,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_disguised_trackers",
        name="{profile_name} Block Disguised Third-Party Trackers",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_disguised_trackers,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="ai_threat_detection",
        name="{profile_name} AI-Driven Threat Detection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.ai_threat_detection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_csam",
        name="{profile_name} Block Child Sexual Abuse Material",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_csam,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_ddns",
        name="{profile_name} Block Dynamic DNS Hostnames",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_ddns,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_nrd",
        name="{profile_name} Block Newly Registered Domains",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_nrd,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_parked_domains",
        name="{profile_name} Block Parked Domains",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_parked_domains,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="cryptojacking_protection",
        name="{profile_name} Cryptojacking Protection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.cryptojacking_protection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="dga_protection",
        name="{profile_name} Domain Generation Algorithms Protection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.dga_protection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="dns_rebinding_protection",
        name="{profile_name} DNS Rebinding Protection",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:dns",
        state=lambda data: data.dns_rebinding_protection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="google_safe_browsing",
        name="{profile_name} Google Safe Browsing",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:google",
        state=lambda data: data.google_safe_browsing,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="idn_homograph_attacks_protection",
        name="{profile_name} IDN Homograph Attacks Protection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.idn_homograph_attacks_protection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="threat_intelligence_feeds",
        name="{profile_name} Threat Intelligence Feeds",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.threat_intelligence_feeds,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="typosquatting_protection",
        name="{profile_name} Typosquatting Protection",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:keyboard-outline",
        state=lambda data: data.typosquatting_protection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_bypass_methods",
        name="{profile_name} Block Bypass Methods",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_bypass_methods,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="safesearch",
        name="{profile_name} Force SafeSearch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:search-web",
        state=lambda data: data.safesearch,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="youtube_restricted_mode",
        name="{profile_name} Force YouTube Restricted Mode",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:youtube",
        state=lambda data: data.youtube_restricted_mode,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add NextDNS entities from a config_entry."""
    coordinator: NextDnsSettingsUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        ATTR_SETTINGS
    ]

    switches: list[NextDnsSwitch] = []
    for description in SWITCHES:
        switches.append(NextDnsSwitch(coordinator, description))

    async_add_entities(switches)


class NextDnsSwitch(CoordinatorEntity[NextDnsSettingsUpdateCoordinator], SwitchEntity):
    """Define an NextDNS switch."""

    def __init__(
        self,
        coordinator: NextDnsSettingsUpdateCoordinator,
        description: NextDnsSwitchEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.profile_id}_{description.key}"
        self._attr_name = cast(str, description.name).format(
            profile_name=coordinator.profile_name
        )
        self._attr_is_on = description.state(coordinator.data)
        self.entity_description: NextDnsSwitchEntityDescription = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.entity_description.state(self.coordinator.data)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        result = await self.coordinator.nextdns.set_setting(
            self.coordinator.profile_id, self.entity_description.key, True
        )

        if result:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        result = await self.coordinator.nextdns.set_setting(
            self.coordinator.profile_id, self.entity_description.key, False
        )

        if result:
            self._attr_is_on = False
            self.async_write_ha_state()
