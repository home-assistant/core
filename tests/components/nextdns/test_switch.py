"""Test switch of NextDNS integration."""
import asyncio
from datetime import timedelta
from unittest.mock import Mock, patch

from aiohttp import ClientError
from aiohttp.client_exceptions import ClientConnectorError
from nextdns import ApiError
import pytest

from homeassistant.components.nextdns.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import SETTINGS, init_integration

from tests.common import async_fire_time_changed


async def test_switch(hass: HomeAssistant) -> None:
    """Test states of the switches."""
    registry = er.async_get(hass)

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_9gag",
        suggested_object_id="fake_profile_block_9gag",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_amazon",
        suggested_object_id="fake_profile_block_amazon",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_blizzard",
        suggested_object_id="fake_profile_block_blizzard",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_dailymotion",
        suggested_object_id="fake_profile_block_dailymotion",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_discord",
        suggested_object_id="fake_profile_block_discord",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_disneyplus",
        suggested_object_id="fake_profile_block_disneyplus",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_ebay",
        suggested_object_id="fake_profile_block_ebay",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_facebook",
        suggested_object_id="fake_profile_block_facebook",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_fortnite",
        suggested_object_id="fake_profile_block_fortnite",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_hulu",
        suggested_object_id="fake_profile_block_hulu",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_imgur",
        suggested_object_id="fake_profile_block_imgur",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_instagram",
        suggested_object_id="fake_profile_block_instagram",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_leagueoflegends",
        suggested_object_id="fake_profile_block_league_of_legends",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_messenger",
        suggested_object_id="fake_profile_block_messenger",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_minecraft",
        suggested_object_id="fake_profile_block_minecraft",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_netflix",
        suggested_object_id="fake_profile_block_netflix",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_pinterest",
        suggested_object_id="fake_profile_block_pinterest",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_primevideo",
        suggested_object_id="fake_profile_block_primevideo",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_reddit",
        suggested_object_id="fake_profile_block_reddit",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_roblox",
        suggested_object_id="fake_profile_block_roblox",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_signal",
        suggested_object_id="fake_profile_block_signal",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_skype",
        suggested_object_id="fake_profile_block_skype",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_snapchat",
        suggested_object_id="fake_profile_block_snapchat",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_spotify",
        suggested_object_id="fake_profile_block_spotify",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_steam",
        suggested_object_id="fake_profile_block_steam",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_telegram",
        suggested_object_id="fake_profile_block_telegram",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_tiktok",
        suggested_object_id="fake_profile_block_tiktok",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_tinder",
        suggested_object_id="fake_profile_block_tinder",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_tumblr",
        suggested_object_id="fake_profile_block_tumblr",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_twitch",
        suggested_object_id="fake_profile_block_twitch",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_twitter",
        suggested_object_id="fake_profile_block_twitter",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_vimeo",
        suggested_object_id="fake_profile_block_vimeo",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_vk",
        suggested_object_id="fake_profile_block_vk",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_whatsapp",
        suggested_object_id="fake_profile_block_whatsapp",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_xboxlive",
        suggested_object_id="fake_profile_block_xboxlive",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_youtube",
        suggested_object_id="fake_profile_block_youtube",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_zoom",
        suggested_object_id="fake_profile_block_zoom",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_dating",
        suggested_object_id="fake_profile_block_dating",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_gambling",
        suggested_object_id="fake_profile_block_gambling",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_piracy",
        suggested_object_id="fake_profile_block_piracy",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_porn",
        suggested_object_id="fake_profile_block_porn",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "xyz12_block_social_networks",
        suggested_object_id="fake_profile_block_social_networks",
        disabled_by=None,
    )

    await init_integration(hass)

    state = hass.states.get("switch.fake_profile_ai_driven_threat_detection")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_ai_driven_threat_detection")
    assert entry
    assert entry.unique_id == "xyz12_ai_threat_detection"

    state = hass.states.get("switch.fake_profile_allow_affiliate_tracking_links")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_allow_affiliate_tracking_links")
    assert entry
    assert entry.unique_id == "xyz12_allow_affiliate"

    state = hass.states.get("switch.fake_profile_anonymized_edns_client_subnet")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_anonymized_edns_client_subnet")
    assert entry
    assert entry.unique_id == "xyz12_anonymized_ecs"

    state = hass.states.get("switch.fake_profile_block_bypass_methods")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_bypass_methods")
    assert entry
    assert entry.unique_id == "xyz12_block_bypass_methods"

    state = hass.states.get("switch.fake_profile_block_child_sexual_abuse_material")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_child_sexual_abuse_material")
    assert entry
    assert entry.unique_id == "xyz12_block_csam"

    state = hass.states.get("switch.fake_profile_block_disguised_third_party_trackers")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get(
        "switch.fake_profile_block_disguised_third_party_trackers"
    )
    assert entry
    assert entry.unique_id == "xyz12_block_disguised_trackers"

    state = hass.states.get("switch.fake_profile_block_dynamic_dns_hostnames")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_dynamic_dns_hostnames")
    assert entry
    assert entry.unique_id == "xyz12_block_ddns"

    state = hass.states.get("switch.fake_profile_block_newly_registered_domains")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_newly_registered_domains")
    assert entry
    assert entry.unique_id == "xyz12_block_nrd"

    state = hass.states.get("switch.fake_profile_block_page")
    assert state
    assert state.state == STATE_OFF

    entry = registry.async_get("switch.fake_profile_block_page")
    assert entry
    assert entry.unique_id == "xyz12_block_page"

    state = hass.states.get("switch.fake_profile_block_parked_domains")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_parked_domains")
    assert entry
    assert entry.unique_id == "xyz12_block_parked_domains"

    state = hass.states.get("switch.fake_profile_cname_flattening")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_cname_flattening")
    assert entry
    assert entry.unique_id == "xyz12_cname_flattening"

    state = hass.states.get("switch.fake_profile_cache_boost")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_cache_boost")
    assert entry
    assert entry.unique_id == "xyz12_cache_boost"

    state = hass.states.get("switch.fake_profile_cryptojacking_protection")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_cryptojacking_protection")
    assert entry
    assert entry.unique_id == "xyz12_cryptojacking_protection"

    state = hass.states.get("switch.fake_profile_dns_rebinding_protection")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_dns_rebinding_protection")
    assert entry
    assert entry.unique_id == "xyz12_dns_rebinding_protection"

    state = hass.states.get(
        "switch.fake_profile_domain_generation_algorithms_protection"
    )
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get(
        "switch.fake_profile_domain_generation_algorithms_protection"
    )
    assert entry
    assert entry.unique_id == "xyz12_dga_protection"

    state = hass.states.get("switch.fake_profile_force_safesearch")
    assert state
    assert state.state == STATE_OFF

    entry = registry.async_get("switch.fake_profile_force_safesearch")
    assert entry
    assert entry.unique_id == "xyz12_safesearch"

    state = hass.states.get("switch.fake_profile_force_youtube_restricted_mode")
    assert state
    assert state.state == STATE_OFF

    entry = registry.async_get("switch.fake_profile_force_youtube_restricted_mode")
    assert entry
    assert entry.unique_id == "xyz12_youtube_restricted_mode"

    state = hass.states.get("switch.fake_profile_google_safe_browsing")
    assert state
    assert state.state == STATE_OFF

    entry = registry.async_get("switch.fake_profile_google_safe_browsing")
    assert entry
    assert entry.unique_id == "xyz12_google_safe_browsing"

    state = hass.states.get("switch.fake_profile_idn_homograph_attacks_protection")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_idn_homograph_attacks_protection")
    assert entry
    assert entry.unique_id == "xyz12_idn_homograph_attacks_protection"

    state = hass.states.get("switch.fake_profile_logs")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_logs")
    assert entry
    assert entry.unique_id == "xyz12_logs"

    state = hass.states.get("switch.fake_profile_threat_intelligence_feeds")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_threat_intelligence_feeds")
    assert entry
    assert entry.unique_id == "xyz12_threat_intelligence_feeds"

    state = hass.states.get("switch.fake_profile_typosquatting_protection")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_typosquatting_protection")
    assert entry
    assert entry.unique_id == "xyz12_typosquatting_protection"

    state = hass.states.get("switch.fake_profile_web3")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_web3")
    assert entry
    assert entry.unique_id == "xyz12_web3"

    state = hass.states.get("switch.fake_profile_block_9gag")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_9gag")
    assert entry
    assert entry.unique_id == "xyz12_block_9gag"

    state = hass.states.get("switch.fake_profile_block_amazon")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_amazon")
    assert entry
    assert entry.unique_id == "xyz12_block_amazon"

    state = hass.states.get("switch.fake_profile_block_blizzard")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_blizzard")
    assert entry
    assert entry.unique_id == "xyz12_block_blizzard"

    state = hass.states.get("switch.fake_profile_block_dailymotion")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_dailymotion")
    assert entry
    assert entry.unique_id == "xyz12_block_dailymotion"

    state = hass.states.get("switch.fake_profile_block_discord")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_discord")
    assert entry
    assert entry.unique_id == "xyz12_block_discord"

    state = hass.states.get("switch.fake_profile_block_disneyplus")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_disneyplus")
    assert entry
    assert entry.unique_id == "xyz12_block_disneyplus"

    state = hass.states.get("switch.fake_profile_block_ebay")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_ebay")
    assert entry
    assert entry.unique_id == "xyz12_block_ebay"

    state = hass.states.get("switch.fake_profile_block_facebook")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_facebook")
    assert entry
    assert entry.unique_id == "xyz12_block_facebook"

    state = hass.states.get("switch.fake_profile_block_fortnite")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_fortnite")
    assert entry
    assert entry.unique_id == "xyz12_block_fortnite"

    state = hass.states.get("switch.fake_profile_block_hulu")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_hulu")
    assert entry
    assert entry.unique_id == "xyz12_block_hulu"

    state = hass.states.get("switch.fake_profile_block_imgur")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_imgur")
    assert entry
    assert entry.unique_id == "xyz12_block_imgur"

    state = hass.states.get("switch.fake_profile_block_instagram")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_instagram")
    assert entry
    assert entry.unique_id == "xyz12_block_instagram"

    state = hass.states.get("switch.fake_profile_block_league_of_legends")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_league_of_legends")
    assert entry
    assert entry.unique_id == "xyz12_block_leagueoflegends"

    state = hass.states.get("switch.fake_profile_block_messenger")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_messenger")
    assert entry
    assert entry.unique_id == "xyz12_block_messenger"

    state = hass.states.get("switch.fake_profile_block_minecraft")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_minecraft")
    assert entry
    assert entry.unique_id == "xyz12_block_minecraft"

    state = hass.states.get("switch.fake_profile_block_netflix")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_netflix")
    assert entry
    assert entry.unique_id == "xyz12_block_netflix"

    state = hass.states.get("switch.fake_profile_block_pinterest")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_pinterest")
    assert entry
    assert entry.unique_id == "xyz12_block_pinterest"

    state = hass.states.get("switch.fake_profile_block_primevideo")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_primevideo")
    assert entry
    assert entry.unique_id == "xyz12_block_primevideo"

    state = hass.states.get("switch.fake_profile_block_reddit")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_reddit")
    assert entry
    assert entry.unique_id == "xyz12_block_reddit"

    state = hass.states.get("switch.fake_profile_block_roblox")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_roblox")
    assert entry
    assert entry.unique_id == "xyz12_block_roblox"

    state = hass.states.get("switch.fake_profile_block_signal")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_signal")
    assert entry
    assert entry.unique_id == "xyz12_block_signal"

    state = hass.states.get("switch.fake_profile_block_skype")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_skype")
    assert entry
    assert entry.unique_id == "xyz12_block_skype"

    state = hass.states.get("switch.fake_profile_block_snapchat")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_snapchat")
    assert entry
    assert entry.unique_id == "xyz12_block_snapchat"

    state = hass.states.get("switch.fake_profile_block_spotify")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_spotify")
    assert entry
    assert entry.unique_id == "xyz12_block_spotify"

    state = hass.states.get("switch.fake_profile_block_steam")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_steam")
    assert entry
    assert entry.unique_id == "xyz12_block_steam"

    state = hass.states.get("switch.fake_profile_block_telegram")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_telegram")
    assert entry
    assert entry.unique_id == "xyz12_block_telegram"

    state = hass.states.get("switch.fake_profile_block_tiktok")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_tiktok")
    assert entry
    assert entry.unique_id == "xyz12_block_tiktok"

    state = hass.states.get("switch.fake_profile_block_tinder")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_tinder")
    assert entry
    assert entry.unique_id == "xyz12_block_tinder"

    state = hass.states.get("switch.fake_profile_block_tumblr")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_tumblr")
    assert entry
    assert entry.unique_id == "xyz12_block_tumblr"

    state = hass.states.get("switch.fake_profile_block_twitch")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_twitch")
    assert entry
    assert entry.unique_id == "xyz12_block_twitch"

    state = hass.states.get("switch.fake_profile_block_twitter")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_twitter")
    assert entry
    assert entry.unique_id == "xyz12_block_twitter"

    state = hass.states.get("switch.fake_profile_block_vimeo")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_vimeo")
    assert entry
    assert entry.unique_id == "xyz12_block_vimeo"

    state = hass.states.get("switch.fake_profile_block_vk")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_vk")
    assert entry
    assert entry.unique_id == "xyz12_block_vk"

    state = hass.states.get("switch.fake_profile_block_whatsapp")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_whatsapp")
    assert entry
    assert entry.unique_id == "xyz12_block_whatsapp"

    state = hass.states.get("switch.fake_profile_block_xboxlive")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_xboxlive")
    assert entry
    assert entry.unique_id == "xyz12_block_xboxlive"

    state = hass.states.get("switch.fake_profile_block_youtube")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_youtube")
    assert entry
    assert entry.unique_id == "xyz12_block_youtube"

    state = hass.states.get("switch.fake_profile_block_zoom")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_zoom")
    assert entry
    assert entry.unique_id == "xyz12_block_zoom"

    state = hass.states.get("switch.fake_profile_block_dating")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_dating")
    assert entry
    assert entry.unique_id == "xyz12_block_dating"

    state = hass.states.get("switch.fake_profile_block_gambling")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_gambling")
    assert entry
    assert entry.unique_id == "xyz12_block_gambling"

    state = hass.states.get("switch.fake_profile_block_piracy")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_piracy")
    assert entry
    assert entry.unique_id == "xyz12_block_piracy"

    state = hass.states.get("switch.fake_profile_block_porn")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_porn")
    assert entry
    assert entry.unique_id == "xyz12_block_porn"

    state = hass.states.get("switch.fake_profile_block_social_networks")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_social_networks")
    assert entry
    assert entry.unique_id == "xyz12_block_social_networks"


async def test_switch_on(hass: HomeAssistant) -> None:
    """Test the switch can be turned on."""
    await init_integration(hass)

    state = hass.states.get("switch.fake_profile_block_page")
    assert state
    assert state.state == STATE_OFF

    with patch(
        "homeassistant.components.nextdns.NextDns.set_setting", return_value=True
    ) as mock_switch_on:
        assert await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.fake_profile_block_page"},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get("switch.fake_profile_block_page")
        assert state
        assert state.state == STATE_ON

        mock_switch_on.assert_called_once()


async def test_switch_off(hass: HomeAssistant) -> None:
    """Test the switch can be turned on."""
    await init_integration(hass)

    state = hass.states.get("switch.fake_profile_web3")
    assert state
    assert state.state == STATE_ON

    with patch(
        "homeassistant.components.nextdns.NextDns.set_setting", return_value=True
    ) as mock_switch_on:
        assert await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.fake_profile_web3"},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get("switch.fake_profile_web3")
        assert state
        assert state.state == STATE_OFF

        mock_switch_on.assert_called_once()


async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entities unavailable correctly when service causes an error."""
    await init_integration(hass)

    state = hass.states.get("switch.fake_profile_web3")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == STATE_ON

    future = utcnow() + timedelta(minutes=10)
    with patch(
        "homeassistant.components.nextdns.NextDns.get_settings",
        side_effect=ApiError("API Error"),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("switch.fake_profile_web3")
    assert state
    assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=20)
    with patch(
        "homeassistant.components.nextdns.NextDns.get_settings",
        return_value=SETTINGS,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("switch.fake_profile_web3")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    "exc",
    [
        ApiError(Mock()),
        asyncio.TimeoutError,
        ClientConnectorError(Mock(), Mock()),
        ClientError,
    ],
)
async def test_switch_failure(hass: HomeAssistant, exc: Exception) -> None:
    """Tests that the turn on/off service throws HomeAssistantError."""
    await init_integration(hass)

    with patch("homeassistant.components.nextdns.NextDns.set_setting", side_effect=exc):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: "switch.fake_profile_block_page"},
                blocking=True,
            )
