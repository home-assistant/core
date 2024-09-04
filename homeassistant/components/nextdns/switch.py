"""Support for the NextDNS service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientError
from aiohttp.client_exceptions import ClientConnectorError
from nextdns import ApiError, Settings

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NextDnsConfigEntry
from .coordinator import NextDnsUpdateCoordinator

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class NextDnsSwitchEntityDescription(SwitchEntityDescription):
    """NextDNS switch entity description."""

    state: Callable[[Settings], bool]


SWITCHES = (
    NextDnsSwitchEntityDescription(
        key="block_page",
        translation_key="block_page",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_page,
    ),
    NextDnsSwitchEntityDescription(
        key="cache_boost",
        translation_key="cache_boost",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.cache_boost,
    ),
    NextDnsSwitchEntityDescription(
        key="cname_flattening",
        translation_key="cname_flattening",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.cname_flattening,
    ),
    NextDnsSwitchEntityDescription(
        key="anonymized_ecs",
        translation_key="anonymized_ecs",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.anonymized_ecs,
    ),
    NextDnsSwitchEntityDescription(
        key="logs",
        translation_key="logs",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.logs,
    ),
    NextDnsSwitchEntityDescription(
        key="web3",
        translation_key="web3",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.web3,
    ),
    NextDnsSwitchEntityDescription(
        key="allow_affiliate",
        translation_key="allow_affiliate",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.allow_affiliate,
    ),
    NextDnsSwitchEntityDescription(
        key="block_disguised_trackers",
        translation_key="block_disguised_trackers",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_disguised_trackers,
    ),
    NextDnsSwitchEntityDescription(
        key="ai_threat_detection",
        translation_key="ai_threat_detection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.ai_threat_detection,
    ),
    NextDnsSwitchEntityDescription(
        key="block_csam",
        translation_key="block_csam",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_csam,
    ),
    NextDnsSwitchEntityDescription(
        key="block_ddns",
        translation_key="block_ddns",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_ddns,
    ),
    NextDnsSwitchEntityDescription(
        key="block_nrd",
        translation_key="block_nrd",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_nrd,
    ),
    NextDnsSwitchEntityDescription(
        key="block_parked_domains",
        translation_key="block_parked_domains",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_parked_domains,
    ),
    NextDnsSwitchEntityDescription(
        key="cryptojacking_protection",
        translation_key="cryptojacking_protection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.cryptojacking_protection,
    ),
    NextDnsSwitchEntityDescription(
        key="dga_protection",
        translation_key="dga_protection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.dga_protection,
    ),
    NextDnsSwitchEntityDescription(
        key="dns_rebinding_protection",
        translation_key="dns_rebinding_protection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.dns_rebinding_protection,
    ),
    NextDnsSwitchEntityDescription(
        key="google_safe_browsing",
        translation_key="google_safe_browsing",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.google_safe_browsing,
    ),
    NextDnsSwitchEntityDescription(
        key="idn_homograph_attacks_protection",
        translation_key="idn_homograph_attacks_protection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.idn_homograph_attacks_protection,
    ),
    NextDnsSwitchEntityDescription(
        key="threat_intelligence_feeds",
        translation_key="threat_intelligence_feeds",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.threat_intelligence_feeds,
    ),
    NextDnsSwitchEntityDescription(
        key="typosquatting_protection",
        translation_key="typosquatting_protection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.typosquatting_protection,
    ),
    NextDnsSwitchEntityDescription(
        key="block_bypass_methods",
        translation_key="block_bypass_methods",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_bypass_methods,
    ),
    NextDnsSwitchEntityDescription(
        key="safesearch",
        translation_key="safesearch",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.safesearch,
    ),
    NextDnsSwitchEntityDescription(
        key="youtube_restricted_mode",
        translation_key="youtube_restricted_mode",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.youtube_restricted_mode,
    ),
    NextDnsSwitchEntityDescription(
        key="block_9gag",
        translation_key="block_9gag",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_9gag,
    ),
    NextDnsSwitchEntityDescription(
        key="block_amazon",
        translation_key="block_amazon",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_amazon,
    ),
    NextDnsSwitchEntityDescription(
        key="block_bereal",
        translation_key="block_bereal",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_bereal,
    ),
    NextDnsSwitchEntityDescription(
        key="block_blizzard",
        translation_key="block_blizzard",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_blizzard,
    ),
    NextDnsSwitchEntityDescription(
        key="block_chatgpt",
        translation_key="block_chatgpt",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_chatgpt,
    ),
    NextDnsSwitchEntityDescription(
        key="block_dailymotion",
        translation_key="block_dailymotion",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_dailymotion,
    ),
    NextDnsSwitchEntityDescription(
        key="block_discord",
        translation_key="block_discord",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_discord,
    ),
    NextDnsSwitchEntityDescription(
        key="block_disneyplus",
        translation_key="block_disneyplus",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_disneyplus,
    ),
    NextDnsSwitchEntityDescription(
        key="block_ebay",
        translation_key="block_ebay",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_ebay,
    ),
    NextDnsSwitchEntityDescription(
        key="block_facebook",
        translation_key="block_facebook",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_facebook,
    ),
    NextDnsSwitchEntityDescription(
        key="block_fortnite",
        translation_key="block_fortnite",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_fortnite,
    ),
    NextDnsSwitchEntityDescription(
        key="block_google_chat",
        translation_key="block_google_chat",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_google_chat,
    ),
    NextDnsSwitchEntityDescription(
        key="block_hbomax",
        translation_key="block_hbomax",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_hbomax,
    ),
    NextDnsSwitchEntityDescription(
        key="block_hulu",
        name="Block Hulu",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_hulu,
    ),
    NextDnsSwitchEntityDescription(
        key="block_imgur",
        translation_key="block_imgur",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_imgur,
    ),
    NextDnsSwitchEntityDescription(
        key="block_instagram",
        translation_key="block_instagram",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_instagram,
    ),
    NextDnsSwitchEntityDescription(
        key="block_leagueoflegends",
        translation_key="block_leagueoflegends",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_leagueoflegends,
    ),
    NextDnsSwitchEntityDescription(
        key="block_mastodon",
        translation_key="block_mastodon",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_mastodon,
    ),
    NextDnsSwitchEntityDescription(
        key="block_messenger",
        translation_key="block_messenger",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_messenger,
    ),
    NextDnsSwitchEntityDescription(
        key="block_minecraft",
        translation_key="block_minecraft",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_minecraft,
    ),
    NextDnsSwitchEntityDescription(
        key="block_netflix",
        translation_key="block_netflix",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_netflix,
    ),
    NextDnsSwitchEntityDescription(
        key="block_pinterest",
        translation_key="block_pinterest",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_pinterest,
    ),
    NextDnsSwitchEntityDescription(
        key="block_playstation_network",
        translation_key="block_playstation_network",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_playstation_network,
    ),
    NextDnsSwitchEntityDescription(
        key="block_primevideo",
        translation_key="block_primevideo",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_primevideo,
    ),
    NextDnsSwitchEntityDescription(
        key="block_reddit",
        translation_key="block_reddit",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_reddit,
    ),
    NextDnsSwitchEntityDescription(
        key="block_roblox",
        translation_key="block_roblox",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_roblox,
    ),
    NextDnsSwitchEntityDescription(
        key="block_signal",
        translation_key="block_signal",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_signal,
    ),
    NextDnsSwitchEntityDescription(
        key="block_skype",
        translation_key="block_skype",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_skype,
    ),
    NextDnsSwitchEntityDescription(
        key="block_snapchat",
        translation_key="block_snapchat",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_snapchat,
    ),
    NextDnsSwitchEntityDescription(
        key="block_spotify",
        translation_key="block_spotify",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_spotify,
    ),
    NextDnsSwitchEntityDescription(
        key="block_steam",
        translation_key="block_steam",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_steam,
    ),
    NextDnsSwitchEntityDescription(
        key="block_telegram",
        translation_key="block_telegram",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_telegram,
    ),
    NextDnsSwitchEntityDescription(
        key="block_tiktok",
        translation_key="block_tiktok",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_tiktok,
    ),
    NextDnsSwitchEntityDescription(
        key="block_tinder",
        translation_key="block_tinder",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_tinder,
    ),
    NextDnsSwitchEntityDescription(
        key="block_tumblr",
        translation_key="block_tumblr",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_tumblr,
    ),
    NextDnsSwitchEntityDescription(
        key="block_twitch",
        translation_key="block_twitch",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_twitch,
    ),
    NextDnsSwitchEntityDescription(
        key="block_twitter",
        translation_key="block_twitter",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_twitter,
    ),
    NextDnsSwitchEntityDescription(
        key="block_vimeo",
        translation_key="block_vimeo",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_vimeo,
    ),
    NextDnsSwitchEntityDescription(
        key="block_vk",
        translation_key="block_vk",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_vk,
    ),
    NextDnsSwitchEntityDescription(
        key="block_whatsapp",
        translation_key="block_whatsapp",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_whatsapp,
    ),
    NextDnsSwitchEntityDescription(
        key="block_xboxlive",
        translation_key="block_xboxlive",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_xboxlive,
    ),
    NextDnsSwitchEntityDescription(
        key="block_youtube",
        translation_key="block_youtube",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_youtube,
    ),
    NextDnsSwitchEntityDescription(
        key="block_zoom",
        translation_key="block_zoom",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_zoom,
    ),
    NextDnsSwitchEntityDescription(
        key="block_dating",
        translation_key="block_dating",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_dating,
    ),
    NextDnsSwitchEntityDescription(
        key="block_gambling",
        translation_key="block_gambling",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_gambling,
    ),
    NextDnsSwitchEntityDescription(
        key="block_online_gaming",
        translation_key="block_online_gaming",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_online_gaming,
    ),
    NextDnsSwitchEntityDescription(
        key="block_piracy",
        translation_key="block_piracy",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_piracy,
    ),
    NextDnsSwitchEntityDescription(
        key="block_porn",
        translation_key="block_porn",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_porn,
    ),
    NextDnsSwitchEntityDescription(
        key="block_social_networks",
        translation_key="block_social_networks",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_social_networks,
    ),
    NextDnsSwitchEntityDescription(
        key="block_video_streaming",
        translation_key="block_video_streaming",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        state=lambda data: data.block_video_streaming,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NextDnsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add NextDNS entities from a config_entry."""
    coordinator = entry.runtime_data.settings

    async_add_entities(
        NextDnsSwitch(coordinator, description) for description in SWITCHES
    )


class NextDnsSwitch(
    CoordinatorEntity[NextDnsUpdateCoordinator[Settings]], SwitchEntity
):
    """Define an NextDNS switch."""

    _attr_has_entity_name = True
    entity_description: NextDnsSwitchEntityDescription

    def __init__(
        self,
        coordinator: NextDnsUpdateCoordinator[Settings],
        description: NextDnsSwitchEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.profile_id}_{description.key}"
        self._attr_is_on = description.state(coordinator.data)
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.entity_description.state(self.coordinator.data)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self.async_set_setting(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self.async_set_setting(False)

    async def async_set_setting(self, new_state: bool) -> None:
        """Set the new state."""
        try:
            result = await self.coordinator.nextdns.set_setting(
                self.coordinator.profile_id, self.entity_description.key, new_state
            )
        except (
            ApiError,
            ClientConnectorError,
            TimeoutError,
            ClientError,
        ) as err:
            raise HomeAssistantError(
                "NextDNS API returned an error calling set_setting for"
                f" {self.entity_id}: {err}"
            ) from err

        if result:
            self._attr_is_on = new_state
            self.async_write_ha_state()
