"""Test NextDNS diagnostics."""
from homeassistant.components.diagnostics import REDACTED

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.components.nextdns import init_integration


async def test_entry_diagnostics(hass, hass_client):
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
        "doq_queries": 10,
        "dot_queries": 30,
        "udp_queries": 40,
        "doh_queries_ratio": 22.2,
        "doq_queries_ratio": 11.1,
        "dot_queries_ratio": 33.3,
        "udp_queries_ratio": 44.4,
    }
    assert result["status_coordinator_data"] == {
        "all_queries": 100,
        "allowed_queries": 30,
        "blocked_queries": 20,
        "default_queries": 40,
        "relayed_queries": 10,
        "blocked_queries_ratio": 20.0,
    }
