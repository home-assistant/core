"""Tests for HKDevice."""

from collections.abc import Callable
import dataclasses
from typing import Any
from unittest import mock

from aiohomekit.controller import TransportType
from aiohomekit.model import Accessories, Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes
from aiohomekit.testing import FakeController
import pytest

from homeassistant.components.climate import ATTR_CURRENT_TEMPERATURE
from homeassistant.components.homekit_controller.connection import (
    MAX_CHARACTERISTICS_PER_REQUEST,
)
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
        # Verify everything is polled (convert to set for comparison since batching changes the type)
        assert set(mock_get_characteristics.call_args_list[0][0][0]) == {
            (1, 10),
            (1, 11),
        }
        assert set(mock_get_characteristics.call_args_list[1][0][0]) == {
            (1, 10),
            (1, 11),
        }

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
        # Verify poll polls all chars
        assert len(mock_get_characteristics.call_args_list[0][0][0]) > 1

        # Now do a manual poll to ensure all chars are polled
        mock_get_characteristics.reset_mock()
        await async_update_entity(hass, helper.entity_id)
        await time_changed(hass, 60)
        await time_changed(hass, DEBOUNCE_COOLDOWN)
        await hass.async_block_till_done()
        assert len(mock_get_characteristics.call_args_list[0][0][0]) > 1


async def test_poll_all_on_startup_refreshes_stale_values(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test that entities get fresh values on startup instead of stale stored values."""
    # Load actual Ecobee accessory fixture
    accessories = await setup_accessories_from_file(hass, "ecobee3.json")

    # Pre-populate storage with the accessories data (already has stale values)
    hass_storage["homekit_controller-entity-map"] = {
        "version": 1,
        "minor_version": 1,
        "key": "homekit_controller-entity-map",
        "data": {
            "pairings": {
                "00:00:00:00:00:00": {
                    "config_num": 1,
                    "accessories": [
                        a.to_accessory_and_service_list() for a in accessories
                    ],
                }
            }
        },
    }

    # Track what gets polled during setup
    polled_chars: list[tuple[int, int]] = []

    # Set up the test accessories
    fake_controller = await setup_platform(hass)

    # Mock get_characteristics to track polling and return fresh temperature
    async def mock_get_characteristics(
        chars: set[tuple[int, int]], **kwargs: Any
    ) -> dict[tuple[int, int], dict[str, Any]]:
        """Return fresh temperature value when polled."""
        polled_chars.extend(chars)
        # Return fresh values for all characteristics
        result: dict[tuple[int, int], dict[str, Any]] = {}
        for aid, iid in chars:
            # Find the characteristic and return appropriate value
            for accessory in accessories:
                if accessory.aid != aid:
                    continue
                for service in accessory.services:
                    for char in service.characteristics:
                        if char.iid != iid:
                            continue
                        # Return fresh temperature instead of stale fixture value
                        if char.type == CharacteristicsTypes.TEMPERATURE_CURRENT:
                            result[(aid, iid)] = {"value": 22.5}  # Fresh value
                        else:
                            result[(aid, iid)] = {"value": char.value}
                        break
        return result

    # Add the paired device with our mock
    await fake_controller.add_paired_device(accessories, "00:00:00:00:00:00")
    config_entry = MockConfigEntry(
        version=1,
        domain="homekit_controller",
        entry_id="TestData",
        data={"AccessoryPairingID": "00:00:00:00:00:00"},
        title="test",
    )
    config_entry.add_to_hass(hass)

    # Get the pairing and patch its get_characteristics
    pairing = fake_controller.pairings["00:00:00:00:00:00"]

    with mock.patch.object(pairing, "get_characteristics", mock_get_characteristics):
        # Set up the config entry (this should trigger poll_all=True)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify that polling happened during setup (poll_all=True was used)
    assert (
        len(polled_chars) == 79
    )  # The Ecobee fixture has exactly 79 readable characteristics

    # Check that the climate entity has the fresh temperature (22.5°C) not the stale fixture value (21.8°C)
    state = hass.states.get("climate.homew")
    assert state is not None
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.5


async def test_characteristic_polling_batching(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that characteristic polling is batched to MAX_CHARACTERISTICS_PER_REQUEST."""

    # Create a large accessory with many characteristics (more than 49)
    def create_large_accessory_with_many_chars(accessory: Accessory) -> None:
        """Create an accessory with many characteristics to test batching."""
        # Add multiple services with many characteristics each
        for service_num in range(10):  # 10 services
            service = accessory.add_service(
                ServicesTypes.LIGHTBULB, name=f"Light {service_num}"
            )
            # Each lightbulb service gets several characteristics
            service.add_char(CharacteristicsTypes.ON)
            service.add_char(CharacteristicsTypes.BRIGHTNESS)
            service.add_char(CharacteristicsTypes.HUE)
            service.add_char(CharacteristicsTypes.SATURATION)
            service.add_char(CharacteristicsTypes.COLOR_TEMPERATURE)
            # Set initial values
            for char in service.characteristics:
                if char.type != CharacteristicsTypes.IDENTIFY:
                    char.value = 0

    helper = await setup_test_component(
        hass, get_next_aid(), create_large_accessory_with_many_chars
    )

    # Track the get_characteristics calls
    get_chars_calls = []
    original_get_chars = helper.pairing.get_characteristics

    async def mock_get_characteristics(chars):
        """Mock get_characteristics to track batch sizes."""
        get_chars_calls.append(list(chars))
        return await original_get_chars(chars)

    # Clear any calls from setup
    get_chars_calls.clear()

    # Patch get_characteristics to track calls
    with mock.patch.object(
        helper.pairing, "get_characteristics", side_effect=mock_get_characteristics
    ):
        # Trigger an update through time_changed which simulates regular polling
        # time_changed expects seconds, not a datetime
        await time_changed(hass, 300)  # 5 minutes in seconds
        await hass.async_block_till_done()

    # We created 10 lightbulb services with 5 characteristics each = 50 total
    # Plus any base accessory characteristics that are pollable
    # This should result in exactly 2 batches
    assert len(get_chars_calls) == 2, (
        f"Should have made exactly 2 batched calls, got {len(get_chars_calls)}"
    )

    # Check that no batch exceeded MAX_CHARACTERISTICS_PER_REQUEST
    for i, batch in enumerate(get_chars_calls):
        assert len(batch) <= MAX_CHARACTERISTICS_PER_REQUEST, (
            f"Batch {i} size {len(batch)} exceeded maximum {MAX_CHARACTERISTICS_PER_REQUEST}"
        )

    # Verify the total number of characteristics polled
    total_chars = sum(len(batch) for batch in get_chars_calls)
    # Each lightbulb has: ON, BRIGHTNESS, HUE, SATURATION, COLOR_TEMPERATURE = 5
    # 10 lightbulbs = 50 characteristics
    assert total_chars == 50, (
        f"Should have polled exactly 50 characteristics, got {total_chars}"
    )

    # The first batch should be full (49 characteristics)
    assert len(get_chars_calls[0]) == 49, (
        f"First batch should have exactly 49 characteristics, got {len(get_chars_calls[0])}"
    )

    # The second batch should have exactly 1 characteristic
    assert len(get_chars_calls[1]) == 1, (
        f"Second batch should have exactly 1 characteristic, got {len(get_chars_calls[1])}"
    )


async def test_async_setup_handles_unparsable_response(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that async_setup handles ValueError from unparsable accessory responses."""
    with caplog.at_level("DEBUG", logger="homeassistant.components.homekit_controller"):
        # Load a simple accessory
        accessories = Accessories()
        accessory = Accessory.create_with_info(
            1, "TestDevice", "example.com", "Test", "0001", "0.1"
        )
        service = accessory.add_service(ServicesTypes.LIGHTBULB)
        on_char = service.add_char(CharacteristicsTypes.ON)
        on_char.value = False
        accessories.add_accessory(accessory)

        async def mock_get_characteristics(
            chars: set[tuple[int, int]], **kwargs: Any
        ) -> dict[tuple[int, int], dict[str, Any]]:
            """Mock that raises ValueError to simulate unparsable response."""
            raise ValueError(
                "Unable to parse text",
                "Error processing token: filename. Filename missing or too long?",
            )

        # Set up the platform and add paired device
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

        # Get the pairing and patch its get_characteristics
        pairing = fake_controller.pairings["00:00:00:00:00:00"]

        with mock.patch.object(
            pairing, "get_characteristics", mock_get_characteristics
        ):
            # Set up the config entry (this will trigger async_setup with poll_all=True)
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        # Verify the debug message was logged
        assert (
            "responded with unparsable response, first update was skipped"
            in caplog.text
        )
        assert "Error processing token: filename" in caplog.text

        # Verify that setup completed (entities were still created despite the polling error)
        # The light entity should exist even though initial polling failed
        state = hass.states.get("light.testdevice")
        assert state is not None
