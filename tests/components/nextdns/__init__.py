"""Tests for the NextDNS integration."""

from contextlib import contextmanager
from unittest.mock import patch

from nextdns import (
    AnalyticsDnssec,
    AnalyticsEncryption,
    AnalyticsIpVersions,
    AnalyticsProtocols,
    AnalyticsStatus,
    ConnectionStatus,
    Settings,
)

from homeassistant.components.nextdns.const import CONF_PROFILE_ID, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONNECTION_STATUS = ConnectionStatus(connected=True, profile_id="abcdef")
PROFILES = [{"id": "xyz12", "fingerprint": "aabbccdd123", "name": "Fake Profile"}]
STATUS = AnalyticsStatus(
    default_queries=40, allowed_queries=30, blocked_queries=20, relayed_queries=10
)
DNSSEC = AnalyticsDnssec(not_validated_queries=25, validated_queries=75)
ENCRYPTION = AnalyticsEncryption(encrypted_queries=60, unencrypted_queries=40)
IP_VERSIONS = AnalyticsIpVersions(ipv4_queries=90, ipv6_queries=10)
PROTOCOLS = AnalyticsProtocols(
    doh_queries=20,
    doh3_queries=15,
    doq_queries=10,
    dot_queries=30,
    tcp_queries=0,
    udp_queries=40,
)
SETTINGS = Settings(
    ai_threat_detection=True,
    allow_affiliate=True,
    anonymized_ecs=True,
    block_bypass_methods=True,
    block_csam=True,
    block_ddns=True,
    block_disguised_trackers=True,
    block_nrd=True,
    block_page=False,
    block_parked_domains=True,
    cache_boost=True,
    cname_flattening=True,
    cryptojacking_protection=True,
    dga_protection=True,
    dns_rebinding_protection=True,
    google_safe_browsing=False,
    idn_homograph_attacks_protection=True,
    logs=True,
    logs_location="ch",
    logs_retention=720,
    safesearch=False,
    threat_intelligence_feeds=True,
    typosquatting_protection=True,
    web3=True,
    youtube_restricted_mode=False,
    block_9gag=True,
    block_amazon=True,
    block_bereal=True,
    block_blizzard=True,
    block_chatgpt=True,
    block_dailymotion=True,
    block_discord=True,
    block_disneyplus=True,
    block_ebay=True,
    block_facebook=True,
    block_fortnite=True,
    block_google_chat=True,
    block_hbomax=True,
    block_hulu=True,
    block_imgur=True,
    block_instagram=True,
    block_leagueoflegends=True,
    block_mastodon=True,
    block_messenger=True,
    block_minecraft=True,
    block_netflix=True,
    block_pinterest=True,
    block_playstation_network=True,
    block_primevideo=True,
    block_reddit=True,
    block_roblox=True,
    block_signal=True,
    block_skype=True,
    block_snapchat=True,
    block_spotify=True,
    block_steam=True,
    block_telegram=True,
    block_tiktok=True,
    block_tinder=True,
    block_tumblr=True,
    block_twitch=True,
    block_twitter=True,
    block_vimeo=True,
    block_vk=True,
    block_whatsapp=True,
    block_xboxlive=True,
    block_youtube=True,
    block_zoom=True,
    block_dating=True,
    block_gambling=True,
    block_online_gaming=True,
    block_piracy=True,
    block_porn=True,
    block_social_networks=True,
    block_video_streaming=True,
)


@contextmanager
def mock_nextdns():
    """Mock the NextDNS class."""
    with (
        patch(
            "homeassistant.components.nextdns.NextDns.get_profiles",
            return_value=PROFILES,
        ),
        patch(
            "homeassistant.components.nextdns.NextDns.get_analytics_status",
            return_value=STATUS,
        ),
        patch(
            "homeassistant.components.nextdns.NextDns.get_analytics_encryption",
            return_value=ENCRYPTION,
        ),
        patch(
            "homeassistant.components.nextdns.NextDns.get_analytics_dnssec",
            return_value=DNSSEC,
        ),
        patch(
            "homeassistant.components.nextdns.NextDns.get_analytics_ip_versions",
            return_value=IP_VERSIONS,
        ),
        patch(
            "homeassistant.components.nextdns.NextDns.get_analytics_protocols",
            return_value=PROTOCOLS,
        ),
        patch(
            "homeassistant.components.nextdns.NextDns.get_settings",
            return_value=SETTINGS,
        ),
        patch(
            "homeassistant.components.nextdns.NextDns.connection_status",
            return_value=CONNECTION_STATUS,
        ),
    ):
        yield


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the NextDNS integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Fake Profile",
        unique_id="xyz12",
        data={CONF_API_KEY: "fake_api_key", CONF_PROFILE_ID: "xyz12"},
        entry_id="d9aa37407ddac7b964a99e86312288d6",
    )

    entry.add_to_hass(hass)

    with mock_nextdns():
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
