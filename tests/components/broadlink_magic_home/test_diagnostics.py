"""Tests for Broadlink Magic Home diagnostics."""

import json

from broadlink_magic import MSG_HEARTBEAT, pack_message
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("socket_enabled")


async def test_diagnostics_exclude_identifiers(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics work and leave out tokens and identifiers."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data
    coordinator.gateway_set.handle_packet(
        "aabbccddeeff",
        pack_message(MSG_HEARTBEAT, 1, bytes.fromhex("aabbccddeeff")),
        ("192.0.2.10", 41001),
    )
    coordinator._handle_fastcon_report(258, b"\x03\x02")

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics["family"]["devices"] == len(coordinator.family.devices)
    assert diagnostics["gateways"] == [
        {"online": True, "has_peer": True},
        {"online": False, "has_peer": False},
    ]
    panel = next(item for item in diagnostics["devices"] if item["short_addr"] == 258)
    assert panel["kind"] == "switch"
    assert panel["reports"] == 1
    dumped = json.dumps(diagnostics)
    for secret in (
        "aabbccddeeff",
        "112233445566",
        "00010203",
        "00112233445566778899aabbccddeeff",
        "family-1",
        "Test home",
        "Living room",
        "192.0.2.10",
    ):
        assert secret not in dumped
