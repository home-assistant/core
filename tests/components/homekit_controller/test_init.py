"""Tests for homekit_controller init."""

from datetime import timedelta
import pathlib
from unittest.mock import patch

from aiohomekit import AccessoryNotFoundError
from aiohomekit.model import Accessory, Transport
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes
from aiohomekit.testing import FakePairing
from attr import asdict
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homekit_controller.const import DOMAIN, ENTITY_MAP
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
    setup_test_accessories_with_controller,
    setup_test_component,
)

from tests.common import async_fire_time_changed
from tests.typing import WebSocketGenerator

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
FIXTURES = [path.relative_to(FIXTURES_DIR) for path in FIXTURES_DIR.glob("*.json")]

ALIVE_DEVICE_NAME = "testdevice"
ALIVE_DEVICE_ENTITY_ID = "light.testdevice"


def create_motion_sensor_service(accessory):
    """Define motion characteristics as per page 225 of HAP spec."""
    service = accessory.add_service(ServicesTypes.MOTION_SENSOR)
    cur_state = service.add_char(CharacteristicsTypes.MOTION_DETECTED)
    cur_state.value = 0


async def test_unload_on_stop(hass: HomeAssistant) -> None:
    """Test async_unload is called on stop."""
    await setup_test_component(hass, create_motion_sensor_service)
    with patch(
        "homeassistant.components.homekit_controller.HKDevice.async_unload"
    ) as async_unlock_mock:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert async_unlock_mock.called


async def test_async_remove_entry(hass: HomeAssistant) -> None:
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


async def test_device_remove_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can only remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})
    helper: Helper = await setup_test_component(hass, create_alive_service)
    config_entry = helper.config_entry
    entry_id = config_entry.entry_id

    entity = entity_registry.entities[ALIVE_DEVICE_ENTITY_ID]

    live_device_entry = device_registry.async_get(entity.device_id)
    client = await hass_ws_client(hass)
    response = await client.remove_device(live_device_entry.id, entry_id)
    assert not response["success"]

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("homekit_controller:accessory-id", "E9:88:E7:B8:B4:40:aid:1")},
    )
    response = await client.remove_device(dead_device_entry.id, entry_id)
    assert response["success"]


async def test_offline_device_raises(hass: HomeAssistant, controller) -> None:
    """Test an offline device raises ConfigEntryNotReady."""

    is_connected = False

    class OfflineFakePairing(FakePairing):
        """Fake pairing that can flip is_connected."""

        @property
        def is_connected(self):
            nonlocal is_connected
            return is_connected

        @property
        def is_available(self):
            return self.is_connected

        async def async_populate_accessories_state(self, *args, **kwargs):
            nonlocal is_connected
            if not is_connected:
                raise AccessoryNotFoundError("any")
            await super().async_populate_accessories_state(*args, **kwargs)

        async def get_characteristics(self, chars, *args, **kwargs):
            nonlocal is_connected
            if not is_connected:
                raise AccessoryNotFoundError("any")
            return {}

    accessory = Accessory.create_with_info(
        "TestDevice", "example.com", "Test", "0001", "0.1"
    )
    create_alive_service(accessory)

    with patch("aiohomekit.testing.FakePairing", OfflineFakePairing):
        await async_setup_component(hass, DOMAIN, {})
        config_entry, _ = await setup_test_accessories_with_controller(
            hass, [accessory], controller
        )
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    is_connected = True

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("light.testdevice").state == STATE_OFF


async def test_ble_device_only_checks_is_available(
    hass: HomeAssistant, controller
) -> None:
    """Test a BLE device only checks is_available."""

    is_available = False

    class FakeBLEPairing(FakePairing):
        """Fake BLE pairing that can flip is_available."""

        @property
        def transport(self):
            return Transport.BLE

        @property
        def is_connected(self):
            return False

        @property
        def is_available(self):
            nonlocal is_available
            return is_available

        async def async_populate_accessories_state(self, *args, **kwargs):
            nonlocal is_available
            if not is_available:
                raise AccessoryNotFoundError("any")
            await super().async_populate_accessories_state(*args, **kwargs)

        async def get_characteristics(self, chars, *args, **kwargs):
            nonlocal is_available
            if not is_available:
                raise AccessoryNotFoundError("any")
            return {}

    accessory = Accessory.create_with_info(
        "TestDevice", "example.com", "Test", "0001", "0.1"
    )
    create_alive_service(accessory)

    with patch("aiohomekit.testing.FakePairing", FakeBLEPairing):
        await async_setup_component(hass, DOMAIN, {})
        config_entry, _ = await setup_test_accessories_with_controller(
            hass, [accessory], controller
        )
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    is_available = True

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("light.testdevice").state == STATE_OFF

    is_available = False
    async_fire_time_changed(hass, utcnow() + timedelta(hours=1))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("light.testdevice").state == STATE_UNAVAILABLE

    is_available = True
    async_fire_time_changed(hass, utcnow() + timedelta(hours=1))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("light.testdevice").state == STATE_OFF


@pytest.mark.parametrize("example", FIXTURES, ids=lambda val: str(val.stem))
async def test_snapshots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    example: str,
) -> None:
    """Detect regressions in enumerating a homekit accessory database and building entities."""
    accessories = await setup_accessories_from_file(hass, example)
    config_entry, _ = await setup_test_accessories(hass, accessories)

    registry_devices = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    registry_devices.sort(key=lambda device: device.name)

    devices = []

    for device in registry_devices:
        entities = []

        registry_entities = er.async_entries_for_device(
            entity_registry,
            device_id=device.id,
            include_disabled_entities=True,
        )
        registry_entities.sort(key=lambda entity: entity.entity_id)

        for entity_entry in registry_entities:
            state_dict = None
            if state := hass.states.get(entity_entry.entity_id):
                state_dict = dict(state.as_dict())
                state_dict.pop("context", None)
                state_dict.pop("last_changed", None)
                state_dict.pop("last_reported", None)
                state_dict.pop("last_updated", None)

                state_dict["attributes"] = dict(state_dict["attributes"])
                state_dict["attributes"].pop("access_token", None)
                state_dict["attributes"].pop("entity_picture", None)

            entry = asdict(entity_entry)
            entry.pop("id", None)
            entry.pop("device_id", None)

            entities.append({"entry": entry, "state": state_dict})

        device_dict = asdict(device)
        device_dict.pop("id", None)
        device_dict.pop("via_device_id", None)
        devices.append({"device": device_dict, "entities": entities})

    assert snapshot == devices
