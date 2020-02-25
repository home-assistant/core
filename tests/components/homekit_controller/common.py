"""Code to support homekit_controller tests."""
from datetime import timedelta
import json
import os
from unittest import mock

from aiohomekit.exceptions import AccessoryNotFoundError
from aiohomekit.model import Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant import config_entries
from homeassistant.components.homekit_controller import config_flow
from homeassistant.components.homekit_controller.const import (
    CONTROLLER,
    DOMAIN,
    HOMEKIT_ACCESSORY_DISPATCH,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture


class FakePairing:
    """
    A test fake that pretends to be a paired HomeKit accessory.

    This only contains methods and values that exist on the upstream Pairing
    class.
    """

    def __init__(self, accessories):
        """Create a fake pairing from an accessory model."""
        self.accessories = accessories
        self.pairing_data = {}
        self.available = True

    async def list_accessories_and_characteristics(self):
        """Fake implementation of list_accessories_and_characteristics."""
        accessories = [a.to_accessory_and_service_list() for a in self.accessories]
        # replicate what happens upstream right now
        self.pairing_data["accessories"] = accessories
        return accessories

    async def get_characteristics(self, characteristics):
        """Fake implementation of get_characteristics."""
        if not self.available:
            raise AccessoryNotFoundError("Accessory not found")

        results = {}
        for aid, cid in characteristics:
            for accessory in self.accessories:
                if aid != accessory.aid:
                    continue
                for service in accessory.services:
                    for char in service.characteristics:
                        if char.iid != cid:
                            continue
                        results[(aid, cid)] = {"value": char.get_value()}
        return results

    async def put_characteristics(self, characteristics):
        """Fake implementation of put_characteristics."""
        for aid, cid, new_val in characteristics:
            for accessory in self.accessories:
                if aid != accessory.aid:
                    continue
                for service in accessory.services:
                    for char in service.characteristics:
                        if char.iid != cid:
                            continue
                        char.set_value(new_val)
        return {}


class FakeController:
    """
    A test fake that pretends to be a paired HomeKit accessory.

    This only contains methods and values that exist on the upstream Controller
    class.
    """

    def __init__(self):
        """Create a Fake controller with no pairings."""
        self.pairings = {}

    def add(self, accessories):
        """Create and register a fake pairing for a simulated accessory."""
        pairing = FakePairing(accessories)
        self.pairings["00:00:00:00:00:00"] = pairing
        return pairing


class Helper:
    """Helper methods for interacting with HomeKit fakes."""

    def __init__(self, hass, entity_id, pairing, accessory, config_entry):
        """Create a helper for a given accessory/entity."""
        self.hass = hass
        self.entity_id = entity_id
        self.pairing = pairing
        self.accessory = accessory
        self.config_entry = config_entry

        self.characteristics = {}
        for service in self.accessory.services:
            service_name = ServicesTypes.get_short(service.type)
            for char in service.characteristics:
                char_name = CharacteristicsTypes.get_short(char.type)
                self.characteristics[(service_name, char_name)] = char

    async def poll_and_get_state(self):
        """Trigger a time based poll and return the current entity state."""
        await time_changed(self.hass, 60)

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
    accessories = Accessory.setup_accessories_from_list(accessories_json)
    return accessories


async def setup_platform(hass):
    """Load the platform but with a fake Controller API."""
    config = {"discovery": {}}

    with mock.patch("aiohomekit.Controller") as controller:
        fake_controller = controller.return_value = FakeController()
        await async_setup_component(hass, DOMAIN, config)

    return fake_controller


async def setup_test_accessories(hass, accessories):
    """Load a fake homekit device based on captured JSON profile."""
    fake_controller = await setup_platform(hass)
    pairing = fake_controller.add(accessories)

    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1},
    }

    pairing.pairing_data.update(
        {"AccessoryPairingID": discovery_info["properties"]["id"]}
    )

    config_entry = MockConfigEntry(
        version=1,
        domain="homekit_controller",
        entry_id="TestData",
        data=pairing.pairing_data,
        title="test",
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
    )

    config_entry.add_to_hass(hass)

    pairing_cls_loc = "homeassistant.components.homekit_controller.connection.IpPairing"
    with mock.patch(pairing_cls_loc) as pairing_cls:
        pairing_cls.return_value = pairing
        await config_entry.async_setup(hass)
        await hass.async_block_till_done()

    return config_entry, pairing


async def device_config_changed(hass, accessories):
    """Discover new devices added to Home Assistant at runtime."""
    # Update the accessories our FakePairing knows about
    controller = hass.data[CONTROLLER]
    pairing = controller.pairings["00:00:00:00:00:00"]
    pairing.accessories = accessories

    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {
            "md": "TestDevice",
            "id": "00:00:00:00:00:00",
            "c#": "2",
            "sf": "0",
        },
    }

    # Config Flow will abort and notify us if the discovery event is of
    # interest - in this case c# has incremented
    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass
    flow.context = {}
    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"

    # Wait for services to reconfigure
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def setup_test_component(hass, setup_accessory, capitalize=False, suffix=None):
    """Load a fake homekit accessory based on a homekit accessory model.

    If capitalize is True, property names will be in upper case.

    If suffix is set, entityId will include the suffix
    """
    accessory = Accessory("TestDevice", "example.com", "Test", "0001", "0.1")
    setup_accessory(accessory)

    domain = None
    for service in accessory.services:
        service_name = ServicesTypes.get_short(service.type)
        if service_name in HOMEKIT_ACCESSORY_DISPATCH:
            domain = HOMEKIT_ACCESSORY_DISPATCH[service_name]
            break

    assert domain, "Cannot map test homekit services to Home Assistant domain"

    config_entry, pairing = await setup_test_accessories(hass, [accessory])
    entity = "testdevice" if suffix is None else "testdevice_{}".format(suffix)
    return Helper(hass, ".".join((domain, entity)), pairing, accessory, config_entry)
