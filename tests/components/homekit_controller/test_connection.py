"""Tests for HKDevice."""

from collections.abc import Callable
import dataclasses
from unittest import mock

from aiohomekit.controller import TransportType
from aiohomekit.model import Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes
from aiohomekit.testing import FakeController
import pytest

from homeassistant.components.homekit_controller.const import (
    DEBOUNCE_COOLDOWN,
    DOMAIN,
    IDENTIFIER_ACCESSORY_ID,
    IDENTIFIER_LEGACY_ACCESSORY_ID,
    IDENTIFIER_LEGACY_SERIAL_NUMBER,
)
from homeassistant.components.thread import async_add_dataset, dataset_store
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from .common import (
    setup_accessories_from_file,
    setup_platform,
    setup_test_accessories,
    setup_test_component,
    time_changed,
)

from tests.common import MockConfigEntry


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
        },
        after={
            (IDENTIFIER_ACCESSORY_ID, "00:00:00:00:00:00:aid:1"),
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
        },
    ),
]


@pytest.mark.parametrize("variant", DEVICE_MIGRATION_TESTS)
async def test_migrate_device_id_no_serial_skip_if_other_owner(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    variant: DeviceMigrationTest,
) -> None:
    """Don't migrate unrelated devices.

    Create a device registry entry that needs migrate, but belongs to a different
    config entry. It should be ignored.
    """
    entry = MockConfigEntry()
    entry.add_to_hass(hass)

    bridge = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
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
    assert bridge.config_entries == {entry.entry_id}


@pytest.mark.parametrize("variant", DEVICE_MIGRATION_TESTS)
async def test_migrate_device_id_no_serial(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    variant: DeviceMigrationTest,
) -> None:
    """Test that a Ryse smart bridge with four shades can be migrated correctly in HA."""
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


async def test_migrate_ble_unique_id(hass: HomeAssistant) -> None:
    """Test that a config entry with incorrect unique_id is repaired."""
    accessories = await setup_accessories_from_file(hass, "anker_eufycam.json")

    fake_controller = await setup_platform(hass)
    await fake_controller.add_paired_device(accessories, "02:03:EF:02:03:EF")
    config_entry = MockConfigEntry(
        version=1,
        domain="homekit_controller",
        entry_id="TestData",
        data={"AccessoryPairingID": "02:03:EF:02:03:EF"},
        title="test",
        unique_id="01:02:AB:01:02:AB",
    )
    config_entry.add_to_hass(hass)

    assert config_entry.unique_id == "01:02:AB:01:02:AB"

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.unique_id == "02:03:ef:02:03:ef"


async def test_thread_provision_no_creds(hass: HomeAssistant) -> None:
    """Test that we don't migrate to thread when there are no creds available."""
    accessories = await setup_accessories_from_file(hass, "nanoleaf_strip_nl55.json")

    fake_controller = await setup_platform(hass)
    await fake_controller.add_paired_device(accessories, "02:03:EF:02:03:EF")
    config_entry = MockConfigEntry(
        version=1,
        domain="homekit_controller",
        entry_id="TestData",
        data={"AccessoryPairingID": "02:03:EF:02:03:EF"},
        title="test",
        unique_id="02:03:ef:02:03:ef",
    )
    config_entry.add_to_hass(hass)

    fake_controller.transport_type = TransportType.BLE

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {
                "entity_id": "button.nanoleaf_strip_3b32_provision_preferred_thread_credentials"
            },
            blocking=True,
        )


async def test_thread_provision(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that a when a thread provision works the config entry is updated."""
    await async_add_dataset(
        hass,
        "Tests",
        "0E080000000000010000000300000F35060004001FFFE0020811111111222222220708FDAD70BF"
        "E5AA15DD051000112233445566778899AABBCCDDEEFF030E4F70656E54687265616444656D6F01"
        "0212340410445F2B5CA6F2A93A55CE570A70EFEECB0C0402A0F7F8",
    )
    store = await dataset_store.async_get_store(hass)
    dataset_id = list(store.datasets.values())[0].id
    store.preferred_dataset = dataset_id

    accessories = await setup_accessories_from_file(hass, "nanoleaf_strip_nl55.json")

    fake_controller = await setup_platform(hass)
    await fake_controller.add_paired_device(accessories, "00:00:00:00:00:00")
    config_entry = MockConfigEntry(
        version=1,
        domain="homekit_controller",
        entry_id="TestData",
        data={"AccessoryPairingID": "00:00:00:00:00:00"},
        title="test",
        unique_id="00:00:00:00:00:00",
    )
    config_entry.add_to_hass(hass)

    fake_controller.transport_type = TransportType.BLE

    # Needs a COAP transport to do migration
    fake_controller.transports = {TransportType.COAP: fake_controller}

    # Fake discovery won't have an address/port - set one so the migration works
    discovery = fake_controller.discoveries["00:00:00:00:00:00"]
    discovery.description.address = "127.0.0.1"
    discovery.description.port = 53

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(
        "button.nanoleaf_strip_3b32_provision_preferred_thread_credentials"
    )
    assert entity_registry.async_get(
        "button.nanoleaf_strip_3b32_provision_preferred_thread_credentials"
    )

    await hass.services.async_call(
        "button",
        "press",
        {
            "entity_id": "button.nanoleaf_strip_3b32_provision_preferred_thread_credentials"
        },
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert config_entry.data["Connection"] == "CoAP"

    assert not hass.states.get(
        "button.nanoleaf_strip_3b32_provision_preferred_thread_credentials"
    )
    assert not entity_registry.async_get(
        "button.nanoleaf_strip_3b32_provision_preferred_thread_credentials"
    )


async def test_thread_provision_migration_failed(hass: HomeAssistant) -> None:
    """Test that when a device 'migrates' but doesn't show up in CoAP, we remain in BLE mode."""
    await async_add_dataset(
        hass,
        "Tests",
        "0E080000000000010000000300000F35060004001FFFE0020811111111222222220708FDAD70BF"
        "E5AA15DD051000112233445566778899AABBCCDDEEFF030E4F70656E54687265616444656D6F01"
        "0212340410445F2B5CA6F2A93A55CE570A70EFEECB0C0402A0F7F8",
    )

    accessories = await setup_accessories_from_file(hass, "nanoleaf_strip_nl55.json")

    fake_controller = await setup_platform(hass)
    await fake_controller.add_paired_device(accessories, "00:00:00:00:00:00")
    config_entry = MockConfigEntry(
        version=1,
        domain="homekit_controller",
        entry_id="TestData",
        data={"AccessoryPairingID": "00:00:00:00:00:00", "Connection": "BLE"},
        title="test",
        unique_id="00:00:00:00:00:00",
    )
    config_entry.add_to_hass(hass)

    fake_controller.transport_type = TransportType.BLE

    # Needs a COAP transport to do migration
    fake_controller.transports = {TransportType.COAP: fake_controller}

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Make sure not disoverable via CoAP
    del fake_controller.discoveries["00:00:00:00:00:00"]

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {
                "entity_id": "button.nanoleaf_strip_3b32_provision_preferred_thread_credentials"
            },
            blocking=True,
        )

    assert config_entry.data["Connection"] == "BLE"


async def test_poll_firmware_version_only_all_watchable_accessory_mode(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we only poll firmware if available and all chars are watchable accessory mode."""

    def _create_accessory(accessory: Accessory) -> Service:
        service = accessory.add_service(ServicesTypes.LIGHTBULB, name="TestDevice")

        on_char = service.add_char(CharacteristicsTypes.ON)
        on_char.value = 0

        brightness = service.add_char(CharacteristicsTypes.BRIGHTNESS)
        brightness.value = 0

        return service

    helper = await setup_test_component(hass, get_next_aid(), _create_accessory)

    with mock.patch.object(
        helper.pairing,
        "get_characteristics",
        wraps=helper.pairing.get_characteristics,
    ) as mock_get_characteristics:
        # Initial state is that the light is off
        state = await helper.poll_and_get_state()
        assert state.state == STATE_OFF
        assert mock_get_characteristics.call_count == 2
        # Verify only firmware version is polled
        assert mock_get_characteristics.call_args_list[0][0][0] == {(1, 7)}
        assert mock_get_characteristics.call_args_list[1][0][0] == {(1, 7)}

        # Test device goes offline
        helper.pairing.available = False
        with mock.patch.object(
            FakeController,
            "async_reachable",
            return_value=False,
        ):
            state = await helper.poll_and_get_state()
            assert state.state == STATE_UNAVAILABLE
            # Tries twice before declaring unavailable
            assert mock_get_characteristics.call_count == 4

        # Test device comes back online
        helper.pairing.available = True
        state = await helper.poll_and_get_state()
        assert state.state == STATE_OFF
        assert mock_get_characteristics.call_count == 6

        # Next poll should not happen because its a single
        # accessory, available, and all chars are watchable
        state = await helper.poll_and_get_state()
        assert state.state == STATE_OFF
        assert mock_get_characteristics.call_count == 8


async def test_manual_poll_all_chars(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that a manual poll will check all chars."""

    def _create_accessory(accessory: Accessory) -> Service:
        service = accessory.add_service(ServicesTypes.LIGHTBULB, name="TestDevice")

        on_char = service.add_char(CharacteristicsTypes.ON)
        on_char.value = 0

        brightness = service.add_char(CharacteristicsTypes.BRIGHTNESS)
        brightness.value = 0

        return service

    helper = await setup_test_component(hass, get_next_aid(), _create_accessory)

    with mock.patch.object(
        helper.pairing,
        "get_characteristics",
        wraps=helper.pairing.get_characteristics,
    ) as mock_get_characteristics:
        # Initial state is that the light is off
        await helper.poll_and_get_state()
        # Verify only firmware version is polled
        assert mock_get_characteristics.call_args_list[0][0][0] == {(1, 7)}

        # Now do a manual poll to ensure all chars are polled
        mock_get_characteristics.reset_mock()
        await async_update_entity(hass, helper.entity_id)
        await time_changed(hass, 60)
        await time_changed(hass, DEBOUNCE_COOLDOWN)
        await hass.async_block_till_done()
        assert len(mock_get_characteristics.call_args_list[0][0][0]) > 1
