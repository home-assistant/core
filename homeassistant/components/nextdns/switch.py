"""Support for the NextDNS service."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NextDnsSettingsUpdateCoordinator
from .const import ATTR_SETTINGS, DOMAIN

PARALLEL_UPDATES = 1

SWITCHES = (
    SwitchEntityDescription(
        key="block_page",
        name="{profile_name} Block Page",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:web-cancel",
    ),
    SwitchEntityDescription(
        key="cache_boost",
        name="{profile_name} Cache Boost",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:memory",
    ),
    SwitchEntityDescription(
        key="cname_flattening",
        name="{profile_name} CNAME Flattening",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:tournament",
    ),
    SwitchEntityDescription(
        key="anonymized_ecs",
        name="{profile_name} Anonymized EDNS Client Subnet",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:incognito",
    ),
    SwitchEntityDescription(
        key="logs",
        name="{profile_name} Logs",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:file-document-outline",
    ),
    SwitchEntityDescription(
        key="web3",
        name="{profile_name} Web3",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:web",
    ),
    SwitchEntityDescription(
        key="allow_affiliate",
        name="{profile_name} Allow Affiliate & Tracking Links",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="block_disguised_trackers",
        name="{profile_name} Block Disguised Third-Party Trackers",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="ai_threat_detection",
        name="{profile_name} AI-Driven Threat Detection",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="block_csam",
        name="{profile_name} Block Child Sexual Abuse Material",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="block_ddns",
        name="{profile_name} Block Dynamic DNS Hostnames",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="block_nrd",
        name="{profile_name} Block Newly Registered Domains",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="block_parked_domains",
        name="{profile_name} Block Parked Domains",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="cryptojacking_protection",
        name="{profile_name} Cryptojacking Protection",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="dga_protection",
        name="{profile_name} Domain Generation Algorithms Protection",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="dns_rebinding_protection",
        name="{profile_name} DNS Rebinding Protection",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:dns",
    ),
    SwitchEntityDescription(
        key="google_safe_browsing",
        name="{profile_name} Google Safe Browsing",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:google",
    ),
    SwitchEntityDescription(
        key="idn_homograph_attacks_protection",
        name="{profile_name} IDN Homograph Attacks Protection",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="threat_intelligence_feeds",
        name="{profile_name} Threat Intelligence Feeds",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="typosquatting_protection",
        name="{profile_name} Typosquatting Protection",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:keyboard-outline",
    ),
    SwitchEntityDescription(
        key="block_bypass_methods",
        name="{profile_name} Block Bypass Methods",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="safesearch",
        name="{profile_name} Force SafeSearch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:search-web",
    ),
    SwitchEntityDescription(
        key="youtube_restricted_mode",
        name="{profile_name} Force YouTube Restricted Mode",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:youtube",
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
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.profile_id}_{description.key}"
        self._attr_name = cast(str, description.name).format(
            profile_name=coordinator.profile_name
        )
        self._attr_is_on = getattr(coordinator.data, description.key)
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = getattr(self.coordinator.data, self.entity_description.key)
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
