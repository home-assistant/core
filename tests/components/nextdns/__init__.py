"""Tests for the NextDNS integration."""
from unittest.mock import patch

from nextdns import (
    AnalyticsDnssec,
    AnalyticsEncryption,
    AnalyticsIpVersions,
    AnalyticsProtocols,
    AnalyticsStatus,
    Settings,
)

from homeassistant.components.nextdns.const import CONF_PROFILE_ID, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

PROFILES = [{"id": "xyz12", "fingerprint": "aabbccdd123", "name": "Fake Profile"}]
STATUS = AnalyticsStatus(
    default_queries=40, allowed_queries=30, blocked_queries=20, relayed_queries=10
)
DNSSEC = AnalyticsDnssec(not_validated_queries=25, validated_queries=75)
ENCRYPTION = AnalyticsEncryption(encrypted_queries=60, unencrypted_queries=40)
IP_VERSIONS = AnalyticsIpVersions(ipv4_queries=90, ipv6_queries=10)
PROTOCOLS = AnalyticsProtocols(
    doh_queries=20,
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
    safesearch=False,
    threat_intelligence_feeds=True,
    typosquatting_protection=True,
    web3=True,
    youtube_restricted_mode=False,
)


async def init_integration(
    hass: HomeAssistant, add_to_hass: bool = True
) -> MockConfigEntry:
    """Set up the NextDNS integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Fake Profile",
        unique_id="xyz12",
        data={CONF_API_KEY: "fake_api_key", CONF_PROFILE_ID: "xyz12"},
    )

    if not add_to_hass:
        return entry

    with patch(
        "homeassistant.components.nextdns.NextDns.get_profiles", return_value=PROFILES
    ), patch(
        "homeassistant.components.nextdns.NextDns.get_analytics_status",
        return_value=STATUS,
    ), patch(
        "homeassistant.components.nextdns.NextDns.get_analytics_encryption",
        return_value=ENCRYPTION,
    ), patch(
        "homeassistant.components.nextdns.NextDns.get_analytics_dnssec",
        return_value=DNSSEC,
    ), patch(
        "homeassistant.components.nextdns.NextDns.get_analytics_ip_versions",
        return_value=IP_VERSIONS,
    ), patch(
        "homeassistant.components.nextdns.NextDns.get_analytics_protocols",
        return_value=PROTOCOLS,
    ), patch(
        "homeassistant.components.nextdns.NextDns.get_settings",
        return_value=SETTINGS,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
