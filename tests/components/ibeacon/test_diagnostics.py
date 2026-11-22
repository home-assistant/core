"""Tests for the iBeacon Tracker diagnostics."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ibeacon.const import (
    CONF_ALLOW_NAMELESS_UUIDS,
    CONF_IGNORE_ADDRESSES,
    CONF_IGNORE_UUIDS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from . import (
    BEACON_RANDOM_ADDRESS_SERVICE_INFO,
    BLUECHARM_BEACON_SERVICE_INFO,
    BLUECHARM_BEACON_SERVICE_INFO_DBUS,
    bluetooth_service_info_replace as replace,
)


@pytest.mark.usefixtures("enable_bluetooth")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IGNORE_ADDRESSES: ["11:22:33:44:55:66"],
            CONF_IGNORE_UUIDS: [
                "22222222-2222-2222-2222-222222222222",
                "00000000-0000-0000-0000-000000000000",
            ],
        },
        options={CONF_ALLOW_NAMELESS_UUIDS: ["11111111-1111-1111-1111-111111111111"]},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, BLUECHARM_BEACON_SERVICE_INFO)
    # Nameless beacons are ignored unless their UUID is allowlisted
    inject_bluetooth_service_info(
        hass,
        replace(
            BLUECHARM_BEACON_SERVICE_INFO_DBUS,
            name=BLUECHARM_BEACON_SERVICE_INFO_DBUS.address,
        ),
    )
    # Rotating the address switches the group to random MAC tracking
    for i in range(10):
        inject_bluetooth_service_info(
            hass,
            replace(
                BEACON_RANDOM_ADDRESS_SERVICE_INFO, address=f"AA:BB:CC:DD:EE:{i:02X}"
            ),
        )
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
