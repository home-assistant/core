"""Tests for homekit_controller init."""

from datetime import timedelta
from unittest.mock import patch

from aiohomekit import exceptions
from aiohomekit.model import Accessories, Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes
from aiohomekit.testing import FakeController, FakeDiscovery, FakePairing

from homeassistant.components.homekit_controller.const import DOMAIN, ENTITY_MAP
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .common import Helper, remove_device

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.homekit_controller.common import setup_test_component

ALIVE_DEVICE_NAME = "testdevice"
ALIVE_DEVICE_ENTITY_ID = "light.testdevice"


def create_motion_sensor_service(accessory):
    """Define motion characteristics as per page 225 of HAP spec."""
    service = accessory.add_service(ServicesTypes.MOTION_SENSOR)
    cur_state = service.add_char(CharacteristicsTypes.MOTION_DETECTED)
    cur_state.value = 0


async def test_unload_on_stop(hass, utcnow):
    """Test async_unload is called on stop."""
    await setup_test_component(hass, create_motion_sensor_service)
    with patch(
        "homeassistant.components.homekit_controller.HKDevice.async_unload"
    ) as async_unlock_mock:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert async_unlock_mock.called


async def test_async_remove_entry(hass: HomeAssistant):
    """Test unpairing a component."""
    helper = await setup_test_component(hass, create_motion_sensor_service)
    controller = helper.pairing.controller

    hkid = "00:00:00:00:00:00"

    assert len(controller.pairings) == 1

    assert hkid in hass.data[ENTITY_MAP].storage_data

    # Remove it via config entry and number of pairings should go down
    await helper.config_entry.async_remove(hass)
    assert len(controller.pairings) == 0

    assert hkid not in hass.data[ENTITY_MAP].storage_data


def create_alive_service(accessory):
    """Create a service to validate we can only remove dead devices."""
    service = accessory.add_service(ServicesTypes.LIGHTBULB, name=ALIVE_DEVICE_NAME)
    service.add_char(CharacteristicsTypes.ON)
    return service


async def test_device_remove_devices(hass, hass_ws_client):
    """Test we can only remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})
    helper: Helper = await setup_test_component(hass, create_alive_service)
    config_entry = helper.config_entry
    entry_id = config_entry.entry_id

    registry: EntityRegistry = er.async_get(hass)
    entity = registry.entities[ALIVE_DEVICE_ENTITY_ID]
    device_registry = dr.async_get(hass)

    live_device_entry = device_registry.async_get(entity.device_id)
    assert (
        await remove_device(await hass_ws_client(hass), live_device_entry.id, entry_id)
        is False
    )

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("homekit_controller:accessory-id", "E9:88:E7:B8:B4:40:aid:1")},
    )
    assert (
        await remove_device(await hass_ws_client(hass), dead_device_entry.id, entry_id)
        is True
    )


async def test_offline_device_raises(hass):
    """Test an offline device raises ConfigEntryNotReady."""

    is_connected = False

    class OfflineFakePairing(FakePairing):
        """Fake pairing that always returns False for is_connected."""

        @property
        def is_connected(self):
            nonlocal is_connected
            return is_connected

    class OfflineFakeDiscovery(FakeDiscovery):
        """Fake discovery that returns an offline pairing."""

        async def start_pairing(self, alias: str):
            if self.description.id in self.controller.pairings:
                raise exceptions.AlreadyPairedError(
                    f"{self.description.id} already paired"
                )

            async def finish_pairing(pairing_code):
                if pairing_code != self.pairing_code:
                    raise exceptions.AuthenticationError("M4")
                pairing_data = {}
                pairing_data["AccessoryIP"] = self.info["address"]
                pairing_data["AccessoryPort"] = self.info["port"]
                pairing_data["Connection"] = "IP"

                obj = self.controller.pairings[alias] = OfflineFakePairing(
                    self.controller, pairing_data, self.accessories
                )
                return obj

            return finish_pairing

    class OfflineFakeController(FakeController):
        """Fake controller that always returns a discovery with a pairing that always returns False for is_connected."""

        def add_device(self, accessories):
            device_id = "00:00:00:00:00:00"
            discovery = self.discoveries[device_id] = OfflineFakeDiscovery(
                self,
                device_id,
                accessories=accessories,
            )
            return discovery

    with patch(
        "homeassistant.components.homekit_controller.utils.Controller"
    ) as controller:
        fake_controller = controller.return_value = OfflineFakeController()
        await async_setup_component(hass, DOMAIN, {})

    pairing_id = "00:00:00:00:00:00"

    accessory = Accessory.create_with_info(
        "TestDevice", "example.com", "Test", "0001", "0.1"
    )
    create_alive_service(accessory)
    accessories_obj = Accessories()
    accessories_obj.add_accessory(accessory)

    await fake_controller.add_paired_device(accessories_obj, pairing_id)

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

    assert config_entry.state == ConfigEntryState.SETUP_RETRY

    is_connected = True

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.LOADED
