"""Tests for the diagnostics data provided by the BTHome integration."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_bluetooth_service_info,
)
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bthome.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import INVALID_PAYLOAD, make_bthome_v2_adv, make_encrypted_bthome_v1_adv

MAC_IN_MANUFACTURER_DATA = BluetoothServiceInfoBleak(
    name="TEST DEVICE 8D18B2",
    address="A4:C1:38:8D:18:B2",
    device=generate_ble_device("A4:C1:38:8D:18:B2", None),
    rssi=-56,
    manufacturer_data={2409: b"\x01\xa4\xc1\x38\x8d\x18\xb2\x02"},
    service_data={
        "0000fcd2-0000-1000-8000-00805f9b34fb": b"\x40\x02\xca\x09\x03\xbf\x13"
    },
    service_uuids=["0000fcd2-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not it"),
    time=0,
    connectable=False,
    tx_power=-127,
)


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
        pytest.param(
            "A4:C1:38:56:53:84",
            {},
            INVALID_PAYLOAD,
            id="mac_in_payload",
        ),
        pytest.param(
            "A4:C1:38:8D:18:B2",
            {},
            MAC_IN_MANUFACTURER_DATA,
            id="mac_in_manufacturer_data",
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
