"""Tests for the NextDNS integration."""
from unittest.mock import patch

from nextdns import (
    AnalyticsDnssec,
    AnalyticsEncryption,
    AnalyticsIpVersions,
    AnalyticsProtocols,
    AnalyticsStatus,
)

from homeassistant.components.nextdns.const import CONF_PROFILE_ID, DOMAIN
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry

PROFILES = [{"id": "xyz12", "fingerprint": "aabbccdd123", "name": "Fake Profile"}]
STATUS = AnalyticsStatus(
    default_queries=40, allowed_queries=30, blocked_queries=20, relayed_queries=10
)
DNSSEC = AnalyticsDnssec(not_validated_queries=25, validated_queries=75)
ENCRYPTION = AnalyticsEncryption(encrypted_queries=60, unencrypted_queries=40)
IP_VERSIONS = AnalyticsIpVersions(ipv4_queries=90, ipv6_queries=10)
PROTOCOLS = AnalyticsProtocols(
    doh_queries=20, doq_queries=10, dot_queries=30, udp_queries=40
)


async def init_integration(hass, add_to_hass=True) -> MockConfigEntry:
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
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
