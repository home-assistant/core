"""Test NextDNS diagnostics."""
from collections.abc import Awaitable, Callable

from aiohttp import ClientSession

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.components.nextdns import init_integration


async def test_entry_diagnostics(
    hass: HomeAssistant, hass_client: Callable[..., Awaitable[ClientSession]]
) -> None:
    """Test config entry diagnostics."""
    entry = await init_integration(hass)

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["config_entry"] == {
        "entry_id": entry.entry_id,
        "version": 1,
        "domain": "nextdns",
        "title": "Fake Profile",
        "data": {"profile_id": REDACTED, "api_key": REDACTED},
        "options": {},
        "pref_disable_new_entities": False,
        "pref_disable_polling": False,
        "source": "user",
        "unique_id": REDACTED,
        "disabled_by": None,
    }
    assert result["dnssec_coordinator_data"] == {
        "not_validated_queries": 25,
        "validated_queries": 75,
        "validated_queries_ratio": 75.0,
    }
    assert result["encryption_coordinator_data"] == {
        "encrypted_queries": 60,
        "unencrypted_queries": 40,
        "encrypted_queries_ratio": 60.0,
    }
    assert result["ip_versions_coordinator_data"] == {
        "ipv6_queries": 10,
        "ipv4_queries": 90,
        "ipv6_queries_ratio": 10.0,
    }
    assert result["protocols_coordinator_data"] == {
        "doh_queries": 20,
        "doh3_queries": 0,
        "doq_queries": 10,
        "dot_queries": 30,
        "tcp_queries": 0,
        "udp_queries": 40,
        "doh_queries_ratio": 20.0,
        "doh3_queries_ratio": 0.0,
        "doq_queries_ratio": 10.0,
        "dot_queries_ratio": 30.0,
        "tcp_queries_ratio": 0.0,
        "udp_queries_ratio": 40.0,
    }
    assert result["settings_coordinator_data"] == {
        "block_page": False,
        "cache_boost": True,
        "cname_flattening": True,
        "anonymized_ecs": True,
        "logs": True,
        "web3": True,
        "allow_affiliate": True,
        "block_disguised_trackers": True,
        "ai_threat_detection": True,
        "block_csam": True,
        "block_ddns": True,
        "block_nrd": True,
        "block_parked_domains": True,
        "cryptojacking_protection": True,
        "dga_protection": True,
        "dns_rebinding_protection": True,
        "google_safe_browsing": False,
        "idn_homograph_attacks_protection": True,
        "threat_intelligence_feeds": True,
        "typosquatting_protection": True,
        "block_bypass_methods": True,
        "safesearch": False,
        "youtube_restricted_mode": True,
        "block_9gag": True,
        "block_amazon": True,
        "block_blizzard": True,
        "block_dailymotion": True,
        "block_discord": True,
        "block_disneyplus": True,
        "block_ebay": True,
        "block_facebook": True,
        "block_fortnite": True,
        "block_hulu": True,
        "block_imgur": True,
        "block_instagram": True,
        "block_leagueoflegends": True,
        "block_messenger": True,
        "block_minecraft": True,
        "block_netflix": True,
        "block_pinterest": True,
        "block_primevideo": True,
        "block_reddit": True,
        "block_roblox": True,
        "block_signal": True,
        "block_skype": True,
        "block_snapchat": True,
        "block_spotify": True,
        "block_steam": True,
        "block_telegram": True,
        "block_tiktok": True,
        "block_tinder": True,
        "block_tumblr": True,
        "block_twitch": True,
        "block_twitter": True,
        "block_vimeo": True,
        "block_vk": True,
        "block_whatsapp": True,
        "block_xboxlive": True,
        "block_youtube": True,
        "block_zoom": True,
        "block_dating": True,
        "block_gambling": True,
        "block_piracy": True,
        "block_porn": True,
        "block_social_networks": True,
    }
    assert result["status_coordinator_data"] == {
        "all_queries": 100,
        "allowed_queries": 30,
        "blocked_queries": 20,
        "default_queries": 40,
        "relayed_queries": 10,
        "blocked_queries_ratio": 20.0,
    }
