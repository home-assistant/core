"""Tests for Shelly binary sensor platform."""

from copy import deepcopy
from unittest.mock import Mock

from aioshelly.const import MODEL_BLU_GATEWAY_G3, MODEL_MOTION
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.shelly.const import DOMAIN, UPDATE_PERIOD_MULTIPLIER
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import (
    MOCK_MAC,
    init_integration,
    mock_rest_update,
    mutate_rpc_device_status,
    patch_platforms,
    register_device,
    register_entity,
    register_sub_device,
)

from tests.common import mock_restore_cache

RELAY_BLOCK_ID = 0
SENSOR_BLOCK_ID = 3


@pytest.fixture(autouse=True)
def fixture_platforms():
    """Limit platforms under test."""
    with patch_platforms([Platform.BINARY_SENSOR]):
        yield


async def test_block_binary_sensor(
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test block binary sensor."""
    monkeypatch.setitem(mock_block_device.shelly, "num_outputs", 1)
    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_overpowering"
    await init_integration(hass, 1)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "overpower", 1)
    mock_block_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-relay_0-overpower"


async def test_block_binary_gas_sensor_creation(
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test block binary gas sensor creation."""
    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_gas"
    await init_integration(hass, 1)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    monkeypatch.setattr(mock_block_device.blocks[SENSOR_BLOCK_ID], "gas", "none")
    mock_block_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-sensor_0-gas"


async def test_block_rest_binary_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test block REST binary sensor."""
    entity_id = register_entity(hass, BINARY_SENSOR_DOMAIN, "test_name_cloud", "cloud")
    monkeypatch.setitem(mock_block_device.status, "cloud", {"connected": False})
    await init_integration(hass, 1)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    monkeypatch.setitem(mock_block_device.status["cloud"], "connected", True)
    await mock_rest_update(hass, freezer)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-cloud"


async def test_block_rest_binary_sensor_connected_battery_devices(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test block REST binary sensor for connected battery devices."""
    entity_id = register_entity(hass, BINARY_SENSOR_DOMAIN, "test_name_cloud", "cloud")
    monkeypatch.setitem(mock_block_device.status, "cloud", {"connected": False})
    monkeypatch.setitem(mock_block_device.settings["device"], "type", MODEL_MOTION)
    monkeypatch.setitem(mock_block_device.settings["coiot"], "update_period", 3600)
    await init_integration(hass, 1, model=MODEL_MOTION)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    monkeypatch.setitem(mock_block_device.status["cloud"], "connected", True)

    # Verify no update on fast intervals
    await mock_rest_update(hass, freezer)
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    # Verify update on slow intervals
    await mock_rest_update(hass, freezer, seconds=UPDATE_PERIOD_MULTIPLIER * 3600)
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-cloud"


async def test_block_sleeping_binary_sensor(
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test block sleeping binary sensor."""
    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_motion"
    await init_integration(hass, 1, sleep_period=1000)

    # Sensor should be created when device is online
    assert hass.states.get(entity_id) is None

    # Make device online
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    monkeypatch.setattr(mock_block_device.blocks[SENSOR_BLOCK_ID], "motion", 1)
    mock_block_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-sensor_0-motion"


async def test_block_restored_sleeping_binary_sensor(
    hass: HomeAssistant,
    mock_block_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block restored sleeping binary sensor."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        "test_name_motion",
        "sensor_0-motion",
        entry,
        device_id=device.id,
    )
    mock_restore_cache(hass, [State(entity_id, STATE_ON)])
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF


async def test_block_restored_sleeping_binary_sensor_no_last_state(
    hass: HomeAssistant,
    mock_block_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block restored sleeping binary sensor missing last state."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        "test_name_motion",
        "sensor_0-motion",
        entry,
        device_id=device.id,
    )
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF


async def test_rpc_binary_sensor(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test RPC binary sensor."""
    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_test_cover_0_overpowering"
    await init_integration(hass, 2)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    mutate_rpc_device_status(
        monkeypatch, mock_rpc_device, "cover:0", "errors", "overpower"
    )
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-cover:0-overpower"


async def test_rpc_binary_sensor_removal(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test RPC binary sensor is removed due to removal_condition."""
    entity_id = register_entity(
        hass, BINARY_SENSOR_DOMAIN, "test_cover_0_input", "input:0-input"
    )

    assert entity_registry.async_get(entity_id) is not None

    monkeypatch.setattr(mock_rpc_device, "status", {"input:0": {"state": False}})
    await init_integration(hass, 2)

    assert entity_registry.async_get(entity_id) is None


async def test_rpc_sleeping_binary_sensor(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test RPC online sleeping binary sensor."""
    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_cloud"
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
    config_entry = await init_integration(hass, 2, sleep_period=1000)

    # Sensor should be created when device is online
    assert hass.states.get(entity_id) is None

    register_entity(
        hass, BINARY_SENSOR_DOMAIN, "test_name_cloud", "cloud-cloud", config_entry
    )

    # Make device online
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cloud", "connected", True)
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    # test external power sensor
    assert (state := hass.states.get("binary_sensor.test_name_external_power"))
    assert state.state == STATE_ON

    assert (
        entry := entity_registry.async_get("binary_sensor.test_name_external_power")
    )
    assert entry.unique_id == "123456789ABC-devicepower:0-external_power"


async def test_rpc_restored_sleeping_binary_sensor(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC restored binary sensor."""
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        "test_name_cloud",
        "cloud-cloud",
        entry,
        device_id=device.id,
    )

    mock_restore_cache(hass, [State(entity_id, STATE_ON)])
    monkeypatch.setattr(mock_rpc_device, "initialized", False)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    # Make device online
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF


async def test_rpc_restored_sleeping_binary_sensor_no_last_state(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC restored sleeping binary sensor missing last state."""
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        "test_name_cloud",
        "cloud-cloud",
        entry,
        device_id=device.id,
    )

    monkeypatch.setattr(mock_rpc_device, "initialized", False)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    # Mock update
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("name", "entity_id"),
    [
        ("Virtual binary sensor", "binary_sensor.test_name_virtual_binary_sensor"),
        (None, "binary_sensor.test_name_boolean_203"),
    ],
)
async def test_rpc_device_virtual_binary_sensor(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    name: str | None,
    entity_id: str,
) -> None:
    """Test a virtual binary sensor for RPC device."""
    config = deepcopy(mock_rpc_device.config)
    config["boolean:203"] = {
        "name": name,
        "meta": {"ui": {"view": "label"}},
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["boolean:203"] = {"value": True}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-boolean:203-boolean_generic"

    monkeypatch.setitem(mock_rpc_device.status["boolean:203"], "value", False)
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("disable_async_remove_shelly_rpc_entities")
async def test_rpc_remove_virtual_binary_sensor_when_mode_toggle(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test if the virtual binary sensor will be removed if the mode has been changed to a toggle."""
    config = deepcopy(mock_rpc_device.config)
    config["boolean:200"] = {"name": None, "meta": {"ui": {"view": "toggle"}}}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["boolean:200"] = {"value": True}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        "test_name_boolean_200",
        "boolean:200-boolean_generic",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is None


async def test_rpc_remove_virtual_binary_sensor_when_orphaned(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
) -> None:
    """Check whether the virtual binary sensor will be removed if it has been removed from the device configuration."""
    config_entry = await init_integration(hass, 3, skip_setup=True)

    # create orphaned entity on main device
    device_entry = register_device(device_registry, config_entry)
    entity_id1 = register_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        "test_name_boolean_200",
        "boolean:200-boolean_generic",
        config_entry,
        device_id=device_entry.id,
    )

    # create orphaned entity on sub device
    sub_device_entry = register_sub_device(
        device_registry,
        config_entry,
        "boolean:201-boolean_generic",
    )
    entity_id2 = register_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        "boolean_201",
        "boolean:201-boolean_generic",
        config_entry,
        device_id=sub_device_entry.id,
    )

    assert entity_registry.async_get(entity_id1) is not None
    assert entity_registry.async_get(entity_id2) is not None

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id1) is None
    assert entity_registry.async_get(entity_id2) is None


async def test_blu_trv_binary_sensor_entity(
    hass: HomeAssistant,
    mock_blu_trv: Mock,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test BLU TRV binary sensor entity."""
    await init_integration(hass, 3, model=MODEL_BLU_GATEWAY_G3)

    for entity in ("calibration",):
        entity_id = f"{BINARY_SENSOR_DOMAIN}.trv_name_{entity}"

        state = hass.states.get(entity_id)
        assert state == snapshot(name=f"{entity_id}-state")

        entry = entity_registry.async_get(entity_id)
        assert entry == snapshot(name=f"{entity_id}-entry")


async def test_rpc_flood_entities(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test RPC flood sensor entities."""
    await init_integration(hass, 4)

    for entity in ("flood", "mute", "cable_unplugged"):
        entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_kitchen_{entity}"

        state = hass.states.get(entity_id)
        assert state == snapshot(name=f"{entity_id}-state")

        entry = entity_registry.async_get(entity_id)
        assert entry == snapshot(name=f"{entity_id}-entry")


async def test_rpc_flood_cable_unplugged(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC flood cable unplugged entity."""
    await init_integration(hass, 4)

    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_kitchen_cable_unplugged"

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    status = deepcopy(mock_rpc_device.status)
    status["flood:0"]["errors"] = ["cable_unplugged"]
    monkeypatch.setattr(mock_rpc_device, "status", status)
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON


async def test_rpc_presence_component(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test RPC binary sensor entity for presence component."""
    config = deepcopy(mock_rpc_device.config)
    config["presence"] = {"enable": True}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["presence"] = {"num_objects": 2}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    mock_config_entry = await init_integration(hass, 4)

    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_occupancy"

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-presence-presence_num_objects"

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "presence", "num_objects", 0)
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    config = deepcopy(mock_rpc_device.config)
    config["presence"] = {"enable": False}
    monkeypatch.setattr(mock_rpc_device, "config", config)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


async def test_rpc_presencezone_component(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test RPC binary sensor entity for presencezone component."""
    config = deepcopy(mock_rpc_device.config)
    config["presencezone:200"] = {"name": "Main zone", "enable": True}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["presencezone:200"] = {"value": True, "num_objects": 3}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    mock_config_entry = await init_integration(hass, 4)

    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_main_zone_occupancy"

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-presencezone:200-presencezone_state"

    mutate_rpc_device_status(
        monkeypatch, mock_rpc_device, "presencezone:200", "value", False
    )
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    config = deepcopy(mock_rpc_device.config)
    config["presencezone:200"] = {"enable": False}
    monkeypatch.setattr(mock_rpc_device, "config", config)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("old_id", "new_id", "role"),
    [
        ("boolean", "boolean_generic", None),
        ("boolean", "boolean_has_power", "has_power"),
        ("input", "input", None),  # negative test, input is not a virtual component
    ],
)
@pytest.mark.usefixtures("disable_async_remove_shelly_rpc_entities")
async def test_migrate_unique_id_virtual_components_roles(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    old_id: str,
    new_id: str,
    role: str | None,
) -> None:
    """Test migration of unique_id for virtual components to include role."""
    entry = await init_integration(hass, 3, skip_setup=True)
    unique_base = f"{MOCK_MAC}-{old_id}:200"
    old_unique_id = f"{unique_base}-{old_id}"
    new_unique_id = f"{unique_base}-{new_id}"
    config = deepcopy(mock_rpc_device.config)
    if role:
        config[f"{old_id}:200"] = {
            "role": role,
        }
    else:
        config[f"{old_id}:200"] = {}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    entity = entity_registry.async_get_or_create(
        suggested_object_id="test_name_test_sensor",
        disabled_by=None,
        domain=BINARY_SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get("binary_sensor.test_name_test_sensor")
    assert entity_entry
    assert entity_entry.unique_id == new_unique_id

    assert (
        "Migrating unique_id for binary_sensor.test_name_test_sensor" in caplog.text
    ) == (old_id != new_id)


async def test_cury_binary_sensor_entity(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test binary sensor entities for cury component."""
    status = {
        "cury:0": {
            "id": 0,
            "slots": {
                "left": {
                    "intensity": 70,
                    "on": True,
                    "boost": None,
                    "vial": {"level": 27, "name": "Forest Dream"},
                },
                "right": {
                    "intensity": 70,
                    "on": False,
                    "boost": {"started_at": 1760365354, "duration": 1800},
                    "vial": {"level": 84, "name": "Velvet Rose"},
                },
            },
        }
    }
    monkeypatch.setattr(mock_rpc_device, "status", status)
    config = {"cury:0": {"id": 0}}
    monkeypatch.setattr(mock_rpc_device, "config", config)
    await init_integration(hass, 3)

    for entity in (
        "left_slot_boost",
        "right_slot_boost",
    ):
        entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_{entity}"

        state = hass.states.get(entity_id)
        assert state == snapshot(name=f"{entity_id}-state")

        entry = entity_registry.async_get(entity_id)
        assert entry == snapshot(name=f"{entity_id}-entry")
