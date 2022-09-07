"""Test NextDNS diagnostics."""
from collections.abc import Awaitable, Callable
import json

from aiohttp import ClientSession

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.common import load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.components.nextdns import init_integration


async def test_entry_diagnostics(
    hass: HomeAssistant, hass_client: Callable[..., Awaitable[ClientSession]]
) -> None:
    """Test config entry diagnostics."""
    settings = json.loads(load_fixture("settings.json", "nextdns"))

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
        "doh3_queries": 15,
        "doq_queries": 10,
        "dot_queries": 30,
        "tcp_queries": 0,
        "udp_queries": 40,
        "doh_queries_ratio": 17.4,
        "doh3_queries_ratio": 13.0,
        "doq_queries_ratio": 8.7,
        "dot_queries_ratio": 26.1,
        "tcp_queries_ratio": 0.0,
        "udp_queries_ratio": 34.8,
    }
    assert result["settings_coordinator_data"] == settings
    assert result["status_coordinator_data"] == {
        "all_queries": 100,
        "allowed_queries": 30,
        "blocked_queries": 20,
        "default_queries": 40,
        "relayed_queries": 10,
        "blocked_queries_ratio": 20.0,
    }
