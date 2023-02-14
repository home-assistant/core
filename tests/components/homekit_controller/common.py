"""Code to support homekit_controller tests."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import json
import logging
import os
from typing import Any, Final
from unittest import mock

from aiohomekit.model import (
    Accessories,
    AccessoriesState,
    Accessory,
    mixin as model_mixin,
)
from aiohomekit.testing import FakeController, FakePairing
from aiohomekit.zeroconf import HomeKitService

from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.homekit_controller.const import (
    CONTROLLER,
    DEBOUNCE_COOLDOWN,
    DOMAIN,
    HOMEKIT_ACCESSORY_DISPATCH,
    IDENTIFIER_ACCESSORY_ID,
)
from homeassistant.components.homekit_controller.utils import async_get_controller
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_get_device_automations,
    load_fixture,
)

logger = logging.getLogger(__name__)


# Root device in test harness always has an accessory id of this
HUB_TEST_ACCESSORY_ID: Final[str] = "00:00:00:00:00:00:aid:1"

TEST_ACCESSORY_ADDRESS = "AA:BB:CC:DD:EE:FF"


TEST_DEVICE_SERVICE_INFO = BluetoothServiceInfo(
    name="test_accessory",
    address=TEST_ACCESSORY_ADDRESS,
    rssi=-56,
    manufacturer_data={},
    service_uuids=["0000ec88-0000-1000-8000-00805f9b34fb"],
    service_data={},
    source="local",
)


@dataclass
class EntityTestInfo:
    """Describes how we expected an entity to be created by homekit_controller."""

    entity_id: str
    unique_id: str
    friendly_name: str
    state: str
    supported_features: int = 0
    capabilities: dict[str, Any] | None = None
    entity_category: EntityCategory | None = None
    unit_of_measurement: str | None = None


@dataclass
class DeviceTriggerInfo:
    """Describe a automation trigger we expect to be created.

    We only use these for a stateless characteristic like a doorbell.
    """

    type: str
    subtype: str


@dataclass
class DeviceTestInfo:
    """Describes how we exepced a device to be created by homekit_controlller."""

    name: str
    manufacturer: str
    model: str
    sw_version: str
    hw_version: str

    devices: list[DeviceTestInfo]
    entities: list[EntityTestInfo]

    # At least one of these must be provided
    unique_id: str | None = None
    serial_number: str | None = None

    # A homekit device can have events but no entity (like a doorbell or remote)
    stateless_triggers: list[DeviceTriggerInfo] | None = None


class Helper:
    """Helper methods for interacting with HomeKit fakes."""

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id: str,
        pairing: FakePairing,
        accessory: Accessory,
        config_entry: ConfigEntry,
    ) -> None:
        """Create a helper for a given accessory/entity."""
        self.hass = hass
        self.entity_id = entity_id
        self.pairing = pairing
        self.accessory = accessory
        self.config_entry = config_entry

    async def async_update(
        self, service: str, characteristics: dict[str, Any]
    ) -> State:
        """Set the characteristics on this service."""
        changes = []

        service = self.accessory.services.first(service_type=service)
        aid = service.accessory.aid

        for ctype, value in characteristics.items():
            char = service.characteristics.first(char_types=[ctype])
            changes.append((aid, char.iid, value))

        self.pairing.testing.update_aid_iid(changes)

        if not self.pairing.testing.events_enabled:
            # If events aren't enabled, explicitly do a poll
            # If they are enabled, then HA will pick up the changes next time
            # we yield control
            await time_changed(self.hass, 60)
            await time_changed(self.hass, DEBOUNCE_COOLDOWN)

        await self.hass.async_block_till_done()

        state = self.hass.states.get(self.entity_id)
        assert state is not None
        return state

    @callback
    def async_assert_service_values(
        self, service: str, characteristics: dict[str, Any]
    ) -> None:
        """Assert a service has characteristics with these values."""
        service = self.accessory.services.first(service_type=service)
        for ctype, value in characteristics.items():
            assert service.value(ctype) == value

    async def poll_and_get_state(self) -> State:
        """Trigger a time based poll and return the current entity state."""
        await time_changed(self.hass, 60)
        await time_changed(self.hass, DEBOUNCE_COOLDOWN)

        state = self.hass.states.get(self.entity_id)
        assert state is not None
        return state


async def time_changed(hass, seconds):
    """Trigger time changed."""
    next_update = dt_util.utcnow() + timedelta(seconds)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()


async def setup_accessories_from_file(hass, path):
    """Load an collection of accessory defs from JSON data."""
    accessories_fixture = await hass.async_add_executor_job(
        load_fixture, os.path.join("homekit_controller", path)
    )
    accessories_json = json.loads(accessories_fixture)
    accessories = Accessories.from_list(accessories_json)
    return accessories


async def setup_platform(hass):
    """Load the platform but with a fake Controller API."""
    config = {"discovery": {}}

    with mock.patch(
        "homeassistant.components.homekit_controller.utils.Controller", FakeController
    ):
        await async_setup_component(hass, DOMAIN, config)

    return await async_get_controller(hass)


async def setup_test_accessories(hass, accessories, connection=None):
    """Load a fake homekit device based on captured JSON profile."""
    fake_controller = await setup_platform(hass)
    return await setup_test_accessories_with_controller(
        hass, accessories, fake_controller, connection
    )


async def setup_test_accessories_with_controller(
    hass, accessories, fake_controller, connection=None
):
    """Load a fake homekit device based on captured JSON profile."""

    pairing_id = "00:00:00:00:00:00"

    accessories_obj = Accessories()
    for accessory in accessories:
        accessories_obj.add_accessory(accessory)
    pairing = await fake_controller.add_paired_device(accessories_obj, pairing_id)

    data = {"AccessoryPairingID": pairing_id}
    if connection == "BLE":
        data["Connection"] = "BLE"
        data["AccessoryAddress"] = TEST_ACCESSORY_ADDRESS

    config_entry = MockConfigEntry(
        version=1,
        domain="homekit_controller",
        entry_id="TestData",
        data=data,
        title="test",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry, pairing


async def device_config_changed(hass, accessories):
    """Discover new devices added to Home Assistant at runtime."""
    # Update the accessories our FakePairing knows about
    controller = hass.data[CONTROLLER]
    pairing = controller.pairings["00:00:00:00:00:00"]

    accessories_obj = Accessories()
    for accessory in accessories:
        accessories_obj.add_accessory(accessory)
    pairing._accessories_state = AccessoriesState(
        accessories_obj, pairing.config_num + 1
    )
    pairing._async_description_update(
        HomeKitService(
            name="TestDevice.local",
            id="00:00:00:00:00:00",
            model="",
            config_num=2,
            state_num=3,
            feature_flags=0,
            status_flags=0,
            category=1,
            protocol_version="1.0",
            type="_hap._tcp.local.",
            address="127.0.0.1",
            addresses=["127.0.0.1"],
            port=8080,
        )
    )

    # Wait for services to reconfigure
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def setup_test_component(
    hass, setup_accessory, capitalize=False, suffix=None, connection=None
):
    """Load a fake homekit accessory based on a homekit accessory model.

    If capitalize is True, property names will be in upper case.

    If suffix is set, entityId will include the suffix
    """
    accessory = Accessory.create_with_info(
        "TestDevice", "example.com", "Test", "0001", "0.1"
    )
    setup_accessory(accessory)

    domain = None
    for service in accessory.services:
        service_name = service.type
        if service_name in HOMEKIT_ACCESSORY_DISPATCH:
            domain = HOMEKIT_ACCESSORY_DISPATCH[service_name]
            break

    assert domain, "Cannot map test homekit services to Home Assistant domain"

    config_entry, pairing = await setup_test_accessories(hass, [accessory], connection)
    entity = "testdevice" if suffix is None else f"testdevice_{suffix}"
    return Helper(hass, ".".join((domain, entity)), pairing, accessory, config_entry)


async def assert_devices_and_entities_created(
    hass: HomeAssistant, expected: DeviceTestInfo
):
    """Check that all expected devices and entities are loaded and enumerated as expected."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    async def _do_assertions(expected: DeviceTestInfo) -> dr.DeviceEntry:
        # Note: homekit_controller currently uses a 3-tuple for device identifiers
        # The current standard is a 2-tuple (hkc was not migrated when this change was brought in)

        # There are currently really 3 cases here:
        # - We can match exactly one device by serial number. This won't work for devices like the Ryse.
        #   These have nlank or broken serial numbers.
        # - The device unique id is "00:00:00:00:00:00" - this is the pairing id. This is only set for
        #   the root (bridge) device.
        # - The device unique id is "00:00:00:00:00:00-X", where X is a HAP aid. This is only set when
        #   we have detected broken serial numbers (and serial number is not used as an identifier).

        device = device_registry.async_get_device(
            {
                (IDENTIFIER_ACCESSORY_ID, expected.unique_id),
            }
        )

        logger.debug("Comparing device %r to %r", device, expected)

        assert device
        assert device.name == expected.name
        assert device.model == expected.model
        assert device.manufacturer == expected.manufacturer
        assert device.hw_version == expected.hw_version
        assert device.sw_version == expected.sw_version

        # We might have matched the device by one identifier only
        # Lets check that the other one is correct. Otherwise the test might silently be wrong.
        accessory_id_set = False

        for key, value in device.identifiers:
            if key == IDENTIFIER_ACCESSORY_ID:
                assert value == expected.unique_id
                accessory_id_set = True

        # If unique_id or serial is provided it MUST actually appear in the device registry entry.
        assert (not expected.unique_id) ^ accessory_id_set

        for entity_info in expected.entities:
            entity = entity_registry.async_get(entity_info.entity_id)
            logger.debug("Comparing entity %r to %r", entity, entity_info)

            assert entity
            assert entity.device_id == device.id
            assert entity.unique_id == entity_info.unique_id
            assert entity.supported_features == entity_info.supported_features
            assert entity.entity_category == entity_info.entity_category
            assert entity.unit_of_measurement == entity_info.unit_of_measurement
            assert entity.capabilities == entity_info.capabilities

            state = hass.states.get(entity_info.entity_id)
            logger.debug("Comparing state %r to %r", state, entity_info)

            assert state is not None
            assert state.state == entity_info.state
            assert state.attributes["friendly_name"] == entity_info.friendly_name

        all_triggers = await async_get_device_automations(
            hass, DeviceAutomationType.TRIGGER, device.id
        )
        stateless_triggers = []
        for trigger in all_triggers:
            if trigger.get("entity_id"):
                continue
            stateless_triggers.append(
                DeviceTriggerInfo(
                    type=trigger.get("type"), subtype=trigger.get("subtype")
                )
            )
        assert stateless_triggers == (expected.stateless_triggers or [])

        for child in expected.devices:
            child_device = await _do_assertions(child)
            assert child_device.via_device_id == device.id
            assert child_device.id != device.id

        return device

    root_device = await _do_assertions(expected)

    # Root device must not have a via, otherwise its not the device
    assert root_device.via_device_id is None


async def remove_device(ws_client, device_id, config_entry_id):
    """Remove config entry from a device."""
    await ws_client.send_json(
        {
            "id": 5,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": config_entry_id,
            "device_id": device_id,
        }
    )
    response = await ws_client.receive_json()
    return response["success"]


def get_next_aid():
    """Get next aid."""
    return model_mixin.id_counter + 1
