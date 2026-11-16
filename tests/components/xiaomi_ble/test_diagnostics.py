"""Tests for the diagnostics data provided by the Xiaomi BLE integration."""

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import (
    inject_bluetooth_service_info_bleak,
)
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.xiaomi_ble.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import make_advertisement


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ED:DE:34:3F:48:0C",
        data={"bindkey": "1330b99cded13258acc391627e9771f7"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "ED:DE:34:3F:48:0C",
            b"\x48\x58\x06\x08\xc9H\x0e\xf1\x12\x81\x07\x973\xfc\x14\x00\x00VD\xdbA",
        ),
    )
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
