"""Tests for HKDevice."""

import dataclasses

import pytest

from homeassistant.components.homekit_controller.const import (
    DOMAIN,
    IDENTIFIER_ACCESSORY_ID,
    IDENTIFIER_LEGACY_ACCESSORY_ID,
    IDENTIFIER_LEGACY_SERIAL_NUMBER,
    IDENTIFIER_SERIAL_NUMBER,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry
from tests.components.homekit_controller.common import (
    setup_accessories_from_file,
    setup_platform,
    setup_test_accessories,
)


@dataclasses.dataclass
class DeviceMigrationTest:
    """Holds the expected state before and after testing a device identifier migration."""

    fixture: str
    manufacturer: str
    before: set[tuple[str, str, str]]
    after: set[tuple[str, str]]


DEVICE_MIGRATION_TESTS = [
    # 0401.3521.0679 was incorrectly treated as a serial number, it should be stripped out during migration
    DeviceMigrationTest(
        fixture="ryse_smart_bridge_four_shades.json",
        manufacturer="RYSE Inc.",
        before={
            (DOMAIN, IDENTIFIER_LEGACY_ACCESSORY_ID, "00:00:00:00:00:00"),
            (DOMAIN, IDENTIFIER_LEGACY_SERIAL_NUMBER, "0401.3521.0679"),
        },
        after={(IDENTIFIER_ACCESSORY_ID, "00:00:00:00:00:00:aid:1")},
    ),
    # This shade has a serial of 1.0.0, which we should already ignore. Make sure it gets migrated to a 2-tuple
    DeviceMigrationTest(
        fixture="ryse_smart_bridge_four_shades.json",
        manufacturer="RYSE Inc.",
        before={
            (DOMAIN, IDENTIFIER_LEGACY_ACCESSORY_ID, "00:00:00:00:00:00_3"),
        },
        after={(IDENTIFIER_ACCESSORY_ID, "00:00:00:00:00:00:aid:3")},
    ),
    # Test migrating a Hue bridge - it has a valid serial number and has an accessory id
    DeviceMigrationTest(
        fixture="hue_bridge.json",
        manufacturer="Philips Lighting",
        before={
            (DOMAIN, IDENTIFIER_LEGACY_ACCESSORY_ID, "00:00:00:00:00:00"),
            (DOMAIN, IDENTIFIER_LEGACY_SERIAL_NUMBER, "123456"),
        },
        after={
            (IDENTIFIER_ACCESSORY_ID, "00:00:00:00:00:00:aid:1"),
            (IDENTIFIER_SERIAL_NUMBER, "123456"),
        },
    ),
    # Test migrating a Hue remote - it has a valid serial number
    # Originally as a non-hub non-broken device it wouldn't have had an accessory id
    DeviceMigrationTest(
        fixture="hue_bridge.json",
        manufacturer="Philips",
        before={
            (DOMAIN, IDENTIFIER_LEGACY_SERIAL_NUMBER, "6623462389072572"),
        },
        after={
            (IDENTIFIER_ACCESSORY_ID, "00:00:00:00:00:00:aid:6623462389072572"),
            (IDENTIFIER_SERIAL_NUMBER, "6623462389072572"),
        },
    ),
    # Test migrating a Koogeek LS1. This is just for completeness (testing hub and hub-less devices)
    DeviceMigrationTest(
        fixture="koogeek_ls1.json",
        manufacturer="Koogeek",
        before={
            (DOMAIN, IDENTIFIER_LEGACY_ACCESSORY_ID, "00:00:00:00:00:00"),
            (DOMAIN, IDENTIFIER_LEGACY_SERIAL_NUMBER, "AAAA011111111111"),
        },
        after={
            (IDENTIFIER_ACCESSORY_ID, "00:00:00:00:00:00:aid:1"),
            (IDENTIFIER_SERIAL_NUMBER, "AAAA011111111111"),
        },
    ),
]


@pytest.mark.parametrize("variant", DEVICE_MIGRATION_TESTS)
async def test_migrate_device_id_no_serial_skip_if_other_owner(
    hass: HomeAssistant, variant: DeviceMigrationTest
):
    """
    Don't migrate unrelated devices.

    Create a device registry entry that needs migrate, but belongs to a different
    config entry. It should be ignored.
    """
    device_registry = dr.async_get(hass)

    bridge = device_registry.async_get_or_create(
        config_entry_id="XX",
        identifiers=variant.before,
        manufacturer="RYSE Inc.",
        model="RYSE SmartBridge",
        name="Wiring Closet",
        sw_version="1.3.0",
        hw_version="0101.2136.0344",
    )

    accessories = await setup_accessories_from_file(hass, variant.fixture)
    await setup_test_accessories(hass, accessories)

    bridge = device_registry.async_get(bridge.id)

    assert bridge.identifiers == variant.before
    assert bridge.config_entries == {"XX"}


@pytest.mark.parametrize("variant", DEVICE_MIGRATION_TESTS)
async def test_migrate_device_id_no_serial(
    hass: HomeAssistant, variant: DeviceMigrationTest
):
    """Test that a Ryse smart bridge with four shades can be migrated correctly in HA."""
    device_registry = dr.async_get(hass)

    accessories = await setup_accessories_from_file(hass, variant.fixture)

    fake_controller = await setup_platform(hass)
    await fake_controller.add_paired_device(accessories, "00:00:00:00:00:00")
    config_entry = MockConfigEntry(
        version=1,
        domain="homekit_controller",
        entry_id="TestData",
        data={"AccessoryPairingID": "00:00:00:00:00:00"},
        title="test",
    )
    config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers=variant.before,
        manufacturer="Dummy Manufacturer",
        model="Dummy Model",
        name="Dummy Name",
        sw_version="99999999991",
        hw_version="99999999999",
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get(device.id)

    assert device.identifiers == variant.after
    assert device.manufacturer == variant.manufacturer
