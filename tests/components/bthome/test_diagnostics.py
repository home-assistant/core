"""Tests for the diagnostics data provided by the BTHome integration."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bthome.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import make_bthome_v2_adv, make_encrypted_bthome_v1_adv


@pytest.mark.parametrize(
    ("address", "data", "advertisement"),
    [
        pytest.param(
            "A4:C1:38:8D:18:B2",
            {},
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x00\x0c\x02\xca\x09\x03\xbf\x13\xf1\x00\x01\x02\x04",
            ),
            id="unencrypted",
        ),
        pytest.param(
            "54:48:E6:8F:80:A5",
            {"bindkey": "231d39c1d7cc1ab1aee224cd096db932"},
            make_encrypted_bthome_v1_adv(
                "54:48:E6:8F:80:A5",
                b'\xfb\xa45\xe4\xd3\xc3\x12\xfb\x00\x11"3W\xd9\n\x99',
            ),
            id="encrypted",
        ),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    address: str,
    data: dict[str, str],
    advertisement: BluetoothServiceInfoBleak,
) -> None:
    """Test diagnostics for a config entry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=address, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, advertisement)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
