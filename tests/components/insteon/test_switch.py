"""Tests for the Insteon scene switches."""

from asyncio import Event
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

from pyinsteon.managers import scene_manager, scene_state_manager
from pyinsteon.managers.scene_state_manager import SceneStateManager
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_load_json_array_fixture,
    mock_restore_cache,
)

from homeassistant.components import insteon
from homeassistant.components.insteon import (
    DOMAIN,
    entity as insteon_entity,
    switch as insteon_switch,
    utils as insteon_utils,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import MOCK_USER_INPUT_PLM
from .mock_devices import MockDevices

EVENING = "switch.evening"
MOVIE = "switch.movie"


@pytest.fixture(autouse=True)
def switch_platform_only():
    """Only set up the switch platform."""
    with patch(
        "homeassistant.components.insteon.INSTEON_PLATFORMS", (Platform.SWITCH,)
    ):
        yield


@pytest.fixture
def devices():
    """Return mock Insteon devices."""
    return MockDevices()


SCENE_LIST = {
    20: {"name": "Evening", "controllers": []},
    21: {"name": "Movie", "controllers": [{"address": "33.33.33", "group": 3}]},
}


@pytest.fixture
def scenes() -> SceneStateManager:
    """Return scene states whose modem trigger sets the scene state."""

    async def trigger(scene_num: int, is_on: bool) -> None:
        manager.triggered.append((scene_num, is_on))
        manager.get(scene_num).set_state(is_on)

    manager = SceneStateManager(trigger)
    manager.triggered = []
    return manager


@pytest.fixture(autouse=True)
def patch_setup(devices: MockDevices, scenes: SceneStateManager) -> Generator[None]:
    """Patch the Insteon connection, devices and scene states."""

    async def load_scene_states(work_dir: str) -> SceneStateManager:
        scenes.update(SCENE_LIST)
        return scenes

    with (
        patch.object(insteon, "async_connect", return_value=True),
        patch.object(insteon, "async_close"),
        patch.object(insteon, "devices", devices),
        patch.object(insteon, "async_load_scene_states", load_scene_states),
        patch.object(insteon_utils, "devices", devices),
        patch.object(insteon_entity, "devices", devices),
        patch.object(insteon_switch, "devices", devices),
        patch.object(scene_state_manager, "devices", devices),
        patch.object(insteon_switch, "async_load_scene_states", load_scene_states),
    ):
        yield


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture(autouse=True)
async def stop_insteon(hass: HomeAssistant):
    """Stop Insteon after each test."""
    yield
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()


async def test_scene_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test each scene has a switch that is not part of a device."""
    await _setup(hass)

    for entity_id, scene_num, name in ((EVENING, 20, "Evening"), (MOVIE, 21, "Movie")):
        entry = entity_registry.async_get(entity_id)
        assert entry.unique_id == f"aaaaaa_scene_{scene_num}"
        assert (entry.device_id, entry.original_name) == (None, name)

    evening = hass.states.get(EVENING)
    assert evening.state == STATE_UNKNOWN
    assert evening.attributes[ATTR_ASSUMED_STATE] is True
    assert evening.attributes[ATTR_FRIENDLY_NAME] == "Evening"


async def test_scenes_discovered_after_device_config(
    hass: HomeAssistant,
    devices: MockDevices,
    scenes: SceneStateManager,
    entity_registry: er.EntityRegistry,
    tmp_path: Path,
) -> None:
    """Create scene switches after uncached device databases have been read."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "insteon_scenes.json").write_text('{"20": "Evening"}')
    aldb_data = await async_load_json_array_fixture(hass, "insteon/scene_data.json")
    await devices.async_load()
    read_started = Event()
    finish_read = Event()

    async def read_device_config() -> None:
        read_started.set()
        await finish_read.wait()
        for device in aldb_data:
            devices.fill_aldb(device["address"], device["aldb"])

    devices.modem.async_read_config.side_effect = read_device_config
    with (
        patch.object(scene_manager, "devices", devices),
        patch.object(scene_manager, "scene_states", scenes),
        patch.object(scene_manager, "_scene_names", {}),
        patch.object(scene_manager.controller_manager, "_scenes", {}),
        patch.object(
            insteon_switch,
            "async_load_scene_states",
            scene_manager.async_load_scene_states,
        ),
        patch.object(
            insteon, "async_load_scene_states", scene_manager.async_load_scene_states
        ),
    ):
        config_entry = await _setup(hass)
        await read_started.wait()
        assert scenes.get(20) is None
        assert hass.states.get(EVENING) is None

        finish_read.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        assert hass.states.get(EVENING).state == STATE_UNKNOWN
        scene_entry = entity_registry.async_get(EVENING)
        assert scene_entry.unique_id == "aaaaaa_scene_20"

        await insteon.async_get_device_config(hass, config_entry)
        await hass.async_block_till_done()
        assert entity_registry.async_get(EVENING) is scene_entry
        assert [
            entry.entity_id
            for entry in entity_registry.entities.values()
            if entry.unique_id.startswith("aaaaaa_scene_")
        ] == [EVENING]


async def test_scene_entities_leave_the_modem(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test scene switches that were part of the modem device are detached."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)
    modem = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "AA.AA.AA")}
    )
    entity_registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "aaaaaa_scene_20",
        config_entry=config_entry,
        device_id=modem.id,
        suggested_object_id="evening",
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(EVENING).device_id is None


async def test_scene_turn_on_off(
    hass: HomeAssistant, scenes: SceneStateManager
) -> None:
    """Test turning a scene on and off triggers it through the modem."""
    await _setup(hass)

    for service, state in ((SERVICE_TURN_ON, STATE_ON), (SERVICE_TURN_OFF, STATE_OFF)):
        await hass.services.async_call(
            SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: EVENING}, blocking=True
        )
        assert hass.states.get(EVENING).state == state
    assert scenes.triggered == [(20, True), (20, False)]


async def test_scene_follows_changes(
    hass: HomeAssistant, scenes: SceneStateManager
) -> None:
    """Test the entity follows scene states and names."""
    await _setup(hass)

    scenes.get(20).set_state(True)
    await hass.async_block_till_done()
    assert hass.states.get(EVENING).state == STATE_ON

    scenes.get(20).update("Late evening", [])
    await hass.async_block_till_done()
    assert hass.states.get(EVENING).attributes[ATTR_FRIENDLY_NAME] == "Late evening"


async def test_scene_follows_keypad_button(
    hass: HomeAssistant, devices: MockDevices
) -> None:
    """Test a keypad-controlled scene follows its button."""
    await _setup(hass)
    assert ATTR_ASSUMED_STATE not in hass.states.get(MOVIE).attributes

    devices["33.33.33"].groups[3].value = True
    await hass.async_block_till_done()
    assert hass.states.get(MOVIE).state == STATE_ON

    devices["33.33.33"].groups[3].value = False
    await hass.async_block_till_done()
    assert hass.states.get(MOVIE).state == STATE_OFF


async def test_scene_restores_state(
    hass: HomeAssistant, scenes: SceneStateManager
) -> None:
    """Test a scene without a known state restores its last state."""
    mock_restore_cache(hass, (State(EVENING, STATE_ON),))
    await _setup(hass)

    assert hass.states.get(EVENING).state == STATE_ON
    assert scenes.get(20).is_on is True


async def test_scenes_added_and_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    scenes: SceneStateManager,
) -> None:
    """Test entities are added for new scenes and removed for deleted scenes."""
    await _setup(hass)

    scenes.update({22: {"name": "Party", "controllers": []}})
    await hass.async_block_till_done()
    assert hass.states.get("switch.party").state == STATE_UNKNOWN

    scenes.update({22: {"name": "Party", "controllers": []}}, deleted=20)
    await hass.async_block_till_done()
    assert entity_registry.async_get(EVENING) is None
    assert hass.states.get(EVENING) is None
