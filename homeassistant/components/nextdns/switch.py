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
        name="Block page",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:web-cancel",
        state=lambda data: data.block_page,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="cache_boost",
        name="Cache boost",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:memory",
        state=lambda data: data.cache_boost,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="cname_flattening",
        name="CNAME flattening",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:tournament",
        state=lambda data: data.cname_flattening,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="anonymized_ecs",
        name="Anonymized EDNS client subnet",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:incognito",
        state=lambda data: data.anonymized_ecs,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="logs",
        name="Logs",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:file-document-outline",
        state=lambda data: data.logs,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="web3",
        name="Web3",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:web",
        state=lambda data: data.web3,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="allow_affiliate",
        name="Allow affiliate & tracking links",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.allow_affiliate,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_disguised_trackers",
        name="Block disguised third-party trackers",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_disguised_trackers,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="ai_threat_detection",
        name="AI-Driven threat detection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.ai_threat_detection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_csam",
        name="Block child sexual abuse material",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_csam,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_ddns",
        name="Block dynamic DNS hostnames",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_ddns,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_nrd",
        name="Block newly registered domains",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_nrd,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_parked_domains",
        name="Block parked domains",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_parked_domains,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="cryptojacking_protection",
        name="Cryptojacking protection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.cryptojacking_protection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="dga_protection",
        name="Domain generation algorithms protection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.dga_protection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="dns_rebinding_protection",
        name="DNS rebinding protection",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:dns",
        state=lambda data: data.dns_rebinding_protection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="google_safe_browsing",
        name="Google safe browsing",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:google",
        state=lambda data: data.google_safe_browsing,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="idn_homograph_attacks_protection",
        name="IDN homograph attacks protection",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.idn_homograph_attacks_protection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="threat_intelligence_feeds",
        name="Threat intelligence feeds",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.threat_intelligence_feeds,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="typosquatting_protection",
        name="Typosquatting protection",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:keyboard-outline",
        state=lambda data: data.typosquatting_protection,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_bypass_methods",
        name="Block bypass methods",
        entity_category=EntityCategory.CONFIG,
        state=lambda data: data.block_bypass_methods,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="safesearch",
        name="Force SafeSearch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:search-web",
        state=lambda data: data.safesearch,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="youtube_restricted_mode",
        name="Force YouTube restricted mode",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:youtube",
        state=lambda data: data.youtube_restricted_mode,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_9gag",
        name="Block 9GAG",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:file-gif-box",
        state=lambda data: data.block_9gag,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_amazon",
        name="Block Amazon",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:cart-outline",
        state=lambda data: data.block_amazon,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_blizzard",
        name="Block Blizzard",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:sword-cross",
        state=lambda data: data.block_blizzard,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_dailymotion",
        name="Block Dailymotion",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:movie-search-outline",
        state=lambda data: data.block_dailymotion,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_discord",
        name="Block Discord",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:message-text",
        state=lambda data: data.block_discord,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_disneyplus",
        name="Block Disney Plus",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:movie-search-outline",
        state=lambda data: data.block_disneyplus,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_ebay",
        name="Block eBay",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:basket-outline",
        state=lambda data: data.block_ebay,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_facebook",
        name="Block Facebook",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:facebook",
        state=lambda data: data.block_facebook,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_fortnite",
        name="Block Fortnite",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:tank",
        state=lambda data: data.block_fortnite,
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
        name="Block Imgur",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:camera-image",
        state=lambda data: data.block_imgur,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_instagram",
        name="Block Instagram",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:instagram",
        state=lambda data: data.block_instagram,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_leagueoflegends",
        name="Block League of Legends",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:sword",
        state=lambda data: data.block_leagueoflegends,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_messenger",
        name="Block Messenger",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:message-text",
        state=lambda data: data.block_messenger,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_minecraft",
        name="Block Minecraft",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:minecraft",
        state=lambda data: data.block_minecraft,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_netflix",
        name="Block Netflix",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:netflix",
        state=lambda data: data.block_netflix,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_pinterest",
        name="Block Pinterest",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:pinterest",
        state=lambda data: data.block_pinterest,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_primevideo",
        name="Block Prime Video",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:filmstrip",
        state=lambda data: data.block_primevideo,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_reddit",
        name="Block Reddit",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:reddit",
        state=lambda data: data.block_reddit,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_roblox",
        name="Block Roblox",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:robot",
        state=lambda data: data.block_roblox,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_signal",
        name="Block Signal",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:chat-outline",
        state=lambda data: data.block_signal,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_skype",
        name="Block Skype",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:skype",
        state=lambda data: data.block_skype,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_snapchat",
        name="Block Snapchat",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:snapchat",
        state=lambda data: data.block_snapchat,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_spotify",
        name="Block Spotify",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:spotify",
        state=lambda data: data.block_spotify,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_steam",
        name="Block Steam",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:steam",
        state=lambda data: data.block_steam,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_telegram",
        name="Block Telegram",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:send-outline",
        state=lambda data: data.block_telegram,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_tiktok",
        name="Block TikTok",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:music-note",
        state=lambda data: data.block_tiktok,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_tinder",
        name="Block Tinder",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:fire",
        state=lambda data: data.block_tinder,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_tumblr",
        name="Block Tumblr",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:image-outline",
        state=lambda data: data.block_tumblr,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_twitch",
        name="Block Twitch",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:twitch",
        state=lambda data: data.block_twitch,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_twitter",
        name="Block Twitter",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:twitter",
        state=lambda data: data.block_twitter,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_vimeo",
        name="Block Vimeo",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:vimeo",
        state=lambda data: data.block_vimeo,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_vk",
        name="Block VK",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:power-socket-eu",
        state=lambda data: data.block_vk,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_whatsapp",
        name="Block WhatsApp",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:whatsapp",
        state=lambda data: data.block_whatsapp,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_xboxlive",
        name="Block Xbox Live",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:microsoft-xbox",
        state=lambda data: data.block_xboxlive,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_youtube",
        name="Block YouTube",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:youtube",
        state=lambda data: data.block_youtube,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_zoom",
        name="Block Zoom",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:video",
        state=lambda data: data.block_zoom,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_dating",
        name="Block dating",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:candelabra",
        state=lambda data: data.block_dating,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_gambling",
        name="Block gambling",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:slot-machine",
        state=lambda data: data.block_gambling,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_piracy",
        name="Block piracy",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:pirate",
        state=lambda data: data.block_piracy,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_porn",
        name="Block porn",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:movie-off",
        state=lambda data: data.block_porn,
    ),
    NextDnsSwitchEntityDescription[Settings](
        key="block_social_networks",
        name="Block social networks",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:facebook",
        state=lambda data: data.block_social_networks,
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
