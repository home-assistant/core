"""Test the ibeacon sensors."""


from dataclasses import replace

import pytest

from homeassistant.components.ibeacon.const import CONF_MIN_RSSI, DOMAIN
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import BLUECHARM_BEACON_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""


async def test_many_groups_same_address_ignored(hass):
    """Test the different uuid, major, minor from many addresses removes all associated entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, BLUECHARM_BEACON_SERVICE_INFO)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.bluecharm_177999_8105_estimated_distance") is not None
    )

    for i in range(12):
        service_info = BluetoothServiceInfo(
            name="BlueCharm_177999",
            address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
            rssi=-63,
            service_data={},
            manufacturer_data={
                76: b"\x02\x15BlueCharmBeacons" + bytearray([i]) + b"\xfe\x13U\xc5"
            },
            service_uuids=[],
            source="local",
        )
        inject_bluetooth_service_info(hass, service_info)

    await hass.async_block_till_done()
    assert hass.states.get("sensor.bluecharm_177999_8105_estimated_distance") is None


async def test_ignore_anything_less_than_min_rssi(hass):
    """Test entities are not created when below the min rssi."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MIN_RSSI: -60},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(
        hass, replace(BLUECHARM_BEACON_SERVICE_INFO, rssi=-100)
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.bluecharm_177999_8105_estimated_distance") is None

    inject_bluetooth_service_info(
        hass,
        replace(
            BLUECHARM_BEACON_SERVICE_INFO,
            rssi=-10,
            service_uuids=["0000180f-0000-1000-8000-00805f9b34fb"],
        ),
    )
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.bluecharm_177999_8105_estimated_distance") is not None
    )


async def test_ignore_not_ibeacons(hass):
    """Test we ignore non-ibeacon data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    before_entity_count = len(hass.states.async_entity_ids())
    inject_bluetooth_service_info(
        hass,
        replace(
            BLUECHARM_BEACON_SERVICE_INFO, manufacturer_data={76: b"\x02\x15invalid"}
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) == before_entity_count
