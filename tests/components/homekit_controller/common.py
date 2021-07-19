"""Code to support homekit_controller tests."""
from datetime import timedelta
import json
import os
from unittest import mock

from aiohomekit.model import Accessories, Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes
from aiohomekit.testing import FakeController

from homeassistant.components.homekit_controller import config_flow
from homeassistant.components.homekit_controller.const import (
    CONTROLLER,
    DOMAIN,
    HOMEKIT_ACCESSORY_DISPATCH,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture


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

    async def update_named_service(self, service, characteristics):
        """Update a service."""
        self.pairing.testing.update_named_service(service, characteristics)
        await self.hass.async_block_till_done()

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
    accessories = Accessories.from_list(accessories_json)
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

    pairing_id = "00:00:00:00:00:00"

    accessories_obj = Accessories()
    for accessory in accessories:
        accessories_obj.add_accessory(accessory)
    pairing = await fake_controller.add_paired_device(accessories_obj, pairing_id)

    config_entry = MockConfigEntry(
        version=1,
        domain="homekit_controller",
        entry_id="TestData",
        data={"AccessoryPairingID": pairing_id},
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
    pairing.accessories = accessories_obj

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
    accessory = Accessory.create_with_info(
        "TestDevice", "example.com", "Test", "0001", "0.1"
    )
    setup_accessory(accessory)

    domain = None
    for service in accessory.services:
        service_name = ServicesTypes.get_short(service.type)
        if service_name in HOMEKIT_ACCESSORY_DISPATCH:
            domain = HOMEKIT_ACCESSORY_DISPATCH[service_name]
            break

    assert domain, "Cannot map test homekit services to Home Assistant domain"

    config_entry, pairing = await setup_test_accessories(hass, [accessory])
    entity = "testdevice" if suffix is None else f"testdevice_{suffix}"
    return Helper(hass, ".".join((domain, entity)), pairing, accessory, config_entry)
