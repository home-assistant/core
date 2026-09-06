"""Test the iZone diagnostics."""

from collections.abc import Callable
from unittest.mock import Mock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.izone.discovery import DATA_DISCOVERY_SERVICE
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Config entry diagnostics include discovery and controller dump_state."""
    entry = init_integration
    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    # Diagnostics JSON round-trips REDACTED to its string form.
    assert result["entry"][CONF_HOST] == str(REDACTED)
    assert result["entry"]["unique_id"] == "000000001"
    assert result["discovery"]["running"] is True
    assert result["discovery"]["udp_bound"] is True
    assert result["discovery"]["claimed"][0]["host"] == str(REDACTED)
    assert result["discovery"]["claimed"][0]["uid"] == "000000001"
    udp = result["discovery"]["recent_udp"][0]
    assert udp["host"] == str(REDACTED)
    assert udp["source_ip"] == str(REDACTED)
    assert entry.runtime_data.controller.device_ip not in udp["message"]
    assert str(REDACTED) in udp["message"]
    assert result["controller"]["device_ip"] == str(REDACTED)
    assert result["controller"]["device_uid"] == "000000001"
    assert result["controller"]["system_settings"]["RAS"] == "master"
    assert result["controller"]["system_settings"]["CtrlZone"] == 1
    assert result["controller"]["zones"][0]["Name"] == "Living Room"
    assert result["controller"]["connected"] is True
    assert result["controller"]["fan_modes"] == ["low", "med", "high", "auto"]
    assert result == snapshot


async def test_config_entry_diagnostics_redacts_discovery_peer_hosts(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    mock_discovery_service: Mock,
) -> None:
    """Hosts from discovery peers are redacted in UDP message payloads."""
    peer_ip = "198.51.100.9"

    def dump_state() -> dict:
        return {
            "closed": False,
            "udp_bound": True,
            "claimed": [
                {
                    "uid": "000000001",
                    "host": "192.0.2.1",
                }
            ],
            "known": [
                {
                    "uid": "000000009",
                    "host": peer_ip,
                }
            ],
            "recent_udp": [
                {
                    "source_ip": peer_ip,
                    "source_port": 12107,
                    "received_at": "2026-07-25T14:37:00.257385+00:00",
                    "message": f"ASPort_12107,Mac_000000009,IP_{peer_ip},iZone",
                    "uid": "000000009",
                    "host": peer_ip,
                    "tags": ["iZone"],
                }
            ],
        }

    mock_discovery_service.dump_state = dump_state

    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert result["discovery"]["known"][0]["host"] == str(REDACTED)
    udp = result["discovery"]["recent_udp"][0]
    assert udp["host"] == str(REDACTED)
    assert udp["source_ip"] == str(REDACTED)
    assert peer_ip not in udp["message"]
    assert str(REDACTED) in udp["message"]


def _pop_discovery_slot(hass: HomeAssistant) -> None:
    """Remove the shared discovery slot entirely."""
    hass.data.pop(DATA_DISCOVERY_SERVICE, None)


def _clear_discovery_runtime(hass: HomeAssistant) -> None:
    """Leave the slot present but with discovery stopped (runtime cleared)."""
    hass.data[DATA_DISCOVERY_SERVICE].runtime = None


@pytest.mark.parametrize(
    "prepare_discovery",
    [
        pytest.param(_pop_discovery_slot, id="slot_absent"),
        pytest.param(_clear_discovery_runtime, id="runtime_stopped"),
    ],
)
async def test_config_entry_diagnostics_without_discovery(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    prepare_discovery: Callable[[HomeAssistant], None],
) -> None:
    """Diagnostics report discovery stopped when discovery is not running."""
    entry = init_integration
    prepare_discovery(hass)

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["discovery"] == {"running": False}
    assert result["entry"][CONF_HOST] == str(REDACTED)
    assert result["entry"]["unique_id"] == "000000001"
    assert result["controller"]["device_uid"] == "000000001"
    assert result["controller"]["device_ip"] == str(REDACTED)
