"""Support for the NextDNS service."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic

from aiohttp import ClientError
from aiohttp.client_exceptions import ClientConnectorError
from nextdns import ApiError, Settings

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CoordinatorDataT, NextDnsSettingsUpdateCoordinator
from .const import ATTR_SETTINGS, DOMAIN

PARALLEL_UPDATES = 1


@dataclass
class NextDnsSwitchRequiredKeysMixin(Generic[CoordinatorDataT]):
    """Class for NextDNS entity required keys."""

    state: Callable[[CoordinatorDataT], bool]


@dataclass
class NextDnsSwitchEntityDescription(
    SwitchEntityDescription, NextDnsSwitchRequiredKeysMixin[CoordinatorDataT]
):
    """NextDNS switch entity description."""


SWITCHES = (
    NextDnsSwitchEntityDescription[Settings](
        key="block_page",
        translation_key="block_page",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:web-cancel",
        state=lambda data: data.block_page,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="cache_boost",
        translation_key="cache_boost",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:memory",
        state=lambda data: data.cache_boost,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="cname_flattening",
        translation_key="cname_flattening",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:tournament",
        state=lambda data: data.cname_flattening,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="anonymized_ecs",
        translation_key="anonymized_ecs",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:incognito",
        state=lambda data: data.anonymized_ecs,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="logs",
        translation_key="logs",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:file-document-outline",
        state=lambda data: data.logs,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="web3",
        translation_key="web3",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:web",
        state=lambda data: data.web3,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="allow_affiliate",
        translation_key="allow_affiliate",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.allow_affiliate,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_disguised_trackers",
        translation_key="block_disguised_trackers",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_disguised_trackers,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="ai_threat_detection",
        translation_key="ai_threat_detection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.ai_threat_detection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_csam",
        translation_key="block_csam",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_csam,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_ddns",
        translation_key="block_ddns",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_ddns,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_nrd",
        translation_key="block_nrd",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_nrd,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_parked_domains",
        translation_key="block_parked_domains",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_parked_domains,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="cryptojacking_protection",
        translation_key="cryptojacking_protection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.cryptojacking_protection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="dga_protection",
        translation_key="dga_protection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.dga_protection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="dns_rebinding_protection",
        translation_key="dns_rebinding_protection",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:dns",
        state=lambda data: data.dns_rebinding_protection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="google_safe_browsing",
        translation_key="google_safe_browsing",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:google",
        state=lambda data: data.google_safe_browsing,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="idn_homograph_attacks_protection",
        translation_key="idn_homograph_attacks_protection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.idn_homograph_attacks_protection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="threat_intelligence_feeds",
        translation_key="threat_intelligence_feeds",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.threat_intelligence_feeds,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="typosquatting_protection",
        translation_key="typosquatting_protection",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:keyboard-outline",
        state=lambda data: data.typosquatting_protection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_bypass_methods",
        translation_key="block_bypass_methods",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_bypass_methods,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="safesearch",
        translation_key="safesearch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:search-web",
        state=lambda data: data.safesearch,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="youtube_restricted_mode",
        translation_key="youtube_restricted_mode",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:youtube",
        state=lambda data: data.youtube_restricted_mode,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_9gag",
        translation_key="block_9gag",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:file-gif-box",
        state=lambda data: data.block_9gag,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_amazon",
        translation_key="block_amazon",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:cart-outline",
        state=lambda data: data.block_amazon,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_bereal",
        translation_key="block_bereal",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:alpha-b-box",
        state=lambda data: data.block_bereal,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_blizzard",
        translation_key="block_blizzard",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:sword-cross",
        state=lambda data: data.block_blizzard,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_chatgpt",
        translation_key="block_chatgpt",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:chat-processing-outline",
        state=lambda data: data.block_chatgpt,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_dailymotion",
        translation_key="block_dailymotion",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:movie-search-outline",
        state=lambda data: data.block_dailymotion,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_discord",
        translation_key="block_discord",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:message-text",
        state=lambda data: data.block_discord,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_disneyplus",
        translation_key="block_disneyplus",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:movie-search-outline",
        state=lambda data: data.block_disneyplus,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_ebay",
        translation_key="block_ebay",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:basket-outline",
        state=lambda data: data.block_ebay,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_facebook",
        translation_key="block_facebook",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:facebook",
        state=lambda data: data.block_facebook,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_fortnite",
        translation_key="block_fortnite",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:tank",
        state=lambda data: data.block_fortnite,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_google_chat",
        translation_key="block_google_chat",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:forum",
        state=lambda data: data.block_google_chat,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_hbomax",
        translation_key="block_hbomax",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:movie-search-outline",
        state=lambda data: data.block_hbomax,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_hulu",
        name="Block Hulu",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:hulu",
        state=lambda data: data.block_hulu,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_imgur",
        translation_key="block_imgur",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:camera-image",
        state=lambda data: data.block_imgur,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_instagram",
        translation_key="block_instagram",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:instagram",
        state=lambda data: data.block_instagram,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_leagueoflegends",
        translation_key="block_leagueoflegends",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:sword",
        state=lambda data: data.block_leagueoflegends,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_mastodon",
        translation_key="block_mastodon",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:mastodon",
        state=lambda data: data.block_mastodon,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_messenger",
        translation_key="block_messenger",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:message-text",
        state=lambda data: data.block_messenger,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_minecraft",
        translation_key="block_minecraft",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:minecraft",
        state=lambda data: data.block_minecraft,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_netflix",
        translation_key="block_netflix",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:netflix",
        state=lambda data: data.block_netflix,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_pinterest",
        translation_key="block_pinterest",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:pinterest",
        state=lambda data: data.block_pinterest,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_playstation_network",
        translation_key="block_playstation_network",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:sony-playstation",
        state=lambda data: data.block_playstation_network,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_primevideo",
        translation_key="block_primevideo",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:filmstrip",
        state=lambda data: data.block_primevideo,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_reddit",
        translation_key="block_reddit",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:reddit",
        state=lambda data: data.block_reddit,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_roblox",
        translation_key="block_roblox",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:robot",
        state=lambda data: data.block_roblox,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_signal",
        translation_key="block_signal",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:chat-outline",
        state=lambda data: data.block_signal,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_skype",
        translation_key="block_skype",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:skype",
        state=lambda data: data.block_skype,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_snapchat",
        translation_key="block_snapchat",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:snapchat",
        state=lambda data: data.block_snapchat,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_spotify",
        translation_key="block_spotify",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:spotify",
        state=lambda data: data.block_spotify,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_steam",
        translation_key="block_steam",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:steam",
        state=lambda data: data.block_steam,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_telegram",
        translation_key="block_telegram",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:send-outline",
        state=lambda data: data.block_telegram,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_tiktok",
        translation_key="block_tiktok",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:music-note",
        state=lambda data: data.block_tiktok,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_tinder",
        translation_key="block_tinder",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:fire",
        state=lambda data: data.block_tinder,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_tumblr",
        translation_key="block_tumblr",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:image-outline",
        state=lambda data: data.block_tumblr,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_twitch",
        translation_key="block_twitch",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:twitch",
        state=lambda data: data.block_twitch,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_twitter",
        translation_key="block_twitter",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:twitter",
        state=lambda data: data.block_twitter,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_vimeo",
        translation_key="block_vimeo",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:vimeo",
        state=lambda data: data.block_vimeo,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_vk",
        translation_key="block_vk",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:power-socket-eu",
        state=lambda data: data.block_vk,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_whatsapp",
        translation_key="block_whatsapp",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:whatsapp",
        state=lambda data: data.block_whatsapp,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_xboxlive",
        translation_key="block_xboxlive",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:microsoft-xbox",
        state=lambda data: data.block_xboxlive,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_youtube",
        translation_key="block_youtube",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:youtube",
        state=lambda data: data.block_youtube,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_zoom",
        translation_key="block_zoom",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:video",
        state=lambda data: data.block_zoom,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_dating",
        translation_key="block_dating",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:candelabra",
        state=lambda data: data.block_dating,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_gambling",
        translation_key="block_gambling",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:slot-machine",
        state=lambda data: data.block_gambling,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_online_gaming",
        translation_key="block_online_gaming",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:gamepad-variant",
        state=lambda data: data.block_online_gaming,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_piracy",
        translation_key="block_piracy",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:pirate",
        state=lambda data: data.block_piracy,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_porn",
        translation_key="block_porn",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:movie-off",
        state=lambda data: data.block_porn,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_social_networks",
        translation_key="block_social_networks",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:facebook",
        state=lambda data: data.block_social_networks,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_video_streaming",
        translation_key="block_video_streaming",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:video-wireless-outline",
        state=lambda data: data.block_video_streaming,
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

    _attr_has_entity_name = True
    entity_description: NextDnsSwitchEntityDescription

    def __init__(
        self,
        coordinator: NextDnsSettingsUpdateCoordinator,
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
            asyncio.TimeoutError,
            ClientError,
        ) as err:
            raise HomeAssistantError(
                "NextDNS API returned an error calling set_setting for"
                f" {self.entity_id}: {err}"
            ) from err

        if result:
            self._attr_is_on = new_state
            self.async_write_ha_state()
