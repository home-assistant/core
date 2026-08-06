"""Test Tewke light."""

from unittest.mock import AsyncMock

import pytest
from pytewke.data import ConfigData, Scene, Target
from pytewke.error import (
    PyTewkeCoapError,
    PyTewkeInvalidRequestError,
    PyTewkeInvalidWallDockError,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.tewke.coordinator import TewkeCoordinatorData
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def mock_tap_with_lights(mock_tap: AsyncMock) -> AsyncMock:
    """Mock tap with lights data."""
    mock_tap.get_config = AsyncMock(
        return_value=ConfigData.model_construct(
            hardware_id="hw123",
            device_name="My Tap",
        )
    )
    mock_tap.get_scenes = AsyncMock(
        return_value={
            "scene1": Scene.model_construct(
                id="scene1",
                name="Morning",
                is_active=True,
                brightness=100,
            ),
            "scene2": Scene.model_construct(
                id="scene2",
                name="Night",
                is_active=False,
                brightness=0,
            ),
        }
    )
    mock_tap.get_targets = AsyncMock(
        return_value={
            1: Target.model_construct(
                name="Main Light",
                is_dimmable=True,
                index=1,
                is_on=True,
                brightness=100,
            ),
            2: Target.model_construct(
                name="Second Light",
                is_dimmable=False,
                index=2,
                is_on=False,
                brightness=0,
            ),
        }
    )
    mock_tap.set_scene = AsyncMock()
    mock_tap.set_target = AsyncMock()
    return mock_tap


async def test_lights(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_tap_with_lights: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation and control of Tewke light entities."""
    mock_config_entry.add_to_hass(hass)

    entity_registry.async_get_or_create(
        LIGHT_DOMAIN,
        "tewke",
        "hw123_target_1",
        suggested_object_id="main_light",
        disabled_by=None,
        config_entry=mock_config_entry,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    light_entities = [ent for ent in entities if ent.domain == LIGHT_DOMAIN]

    assert len(light_entities) == 4

    for entity_entry in light_entities:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        state = hass.states.get(entity_entry.entity_id)
        if entity_entry.disabled_by:
            assert state is None
        else:
            assert state is not None
            assert state == snapshot(name=f"{entity_entry.entity_id}-state")

    # Turn on scene1
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.living_room_tewke_switch_morning",
            ATTR_BRIGHTNESS: 255,
        },
        blocking=True,
    )
    mock_tap_with_lights.set_scene.assert_called_with(
        scene_id="scene1", state=True, brightness=100
    )
    mock_tap_with_lights.set_scene.reset_mock()

    # Turn off scene1
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.living_room_tewke_switch_morning"},
        blocking=True,
    )
    mock_tap_with_lights.set_scene.assert_called_with(
        scene_id="scene1", state=False, brightness=None
    )

    # Turn off target1
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.main_light"},
        blocking=True,
    )
    mock_tap_with_lights.set_target.assert_called_with(target=1, brightness=0)
    mock_tap_with_lights.set_target.reset_mock()

    # Turn on target1 without brightness (dimmable, currently 0, should default to 100)
    # Note: the mock state doesn't update unless we mock the refresh, but our code sets self._brightness internally
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.main_light"},
        blocking=True,
    )
    mock_tap_with_lights.set_target.assert_called_with(target=1, brightness=100)
    mock_tap_with_lights.set_target.reset_mock()

    # Turn on target1 again without brightness (dimmable, currently 100, should keep 100)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.main_light"},
        blocking=True,
    )
    mock_tap_with_lights.set_target.assert_called_with(target=1, brightness=100)
    mock_tap_with_lights.set_target.reset_mock()

    # Turn on target1 with explicit brightness
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.main_light",
            ATTR_BRIGHTNESS: 128,
        },
        blocking=True,
    )
    mock_tap_with_lights.set_target.assert_called_with(target=1, brightness=50)
    mock_tap_with_lights.set_target.reset_mock()

    # Enable and setup target2 to test non-dimmable light
    target2_entity_id = entity_registry.async_get_entity_id(
        LIGHT_DOMAIN, "tewke", "hw123_target_2"
    )
    entity_registry.async_update_entity(target2_entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Turn on target2 (non-dimmable, defaults to 100)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: target2_entity_id},
        blocking=True,
    )
    mock_tap_with_lights.set_target.assert_called_with(target=2, brightness=100)
    mock_tap_with_lights.set_target.reset_mock()

    # Check brightness of non-dimmable
    state = hass.states.get(target2_entity_id)
    assert state.attributes.get(ATTR_BRIGHTNESS) is None


async def test_light_availability(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_tap_with_lights: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the availability of Tewke light entities."""
    mock_config_entry.add_to_hass(hass)

    target1_entity_id = entity_registry.async_get_or_create(
        LIGHT_DOMAIN,
        "tewke",
        "hw123_target_1",
        suggested_object_id="main_light",
        disabled_by=None,
        config_entry=mock_config_entry,
    ).entity_id

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify initially available
    assert hass.states.get(target1_entity_id).state != "unavailable"
    assert (
        hass.states.get("light.living_room_tewke_switch_morning").state != "unavailable"
    )

    # Remove target1 and scene1 from coordinator data to test availability
    coordinator = mock_config_entry.runtime_data.coordinator

    new_data = TewkeCoordinatorData(
        scenes={},
        targets={
            2: Target.model_construct(
                name="Second Light",
                is_dimmable=False,
                index=2,
                is_on=False,
                brightness=0,
            ),
        },
        sensors=coordinator.data["sensors"],
        radar=coordinator.data["radar"],
        energy=coordinator.data["energy"],
        energy_override=coordinator.data["energy_override"],
        config=coordinator.data["config"],
    )

    coordinator.async_set_updated_data(new_data)

    assert hass.states.get(target1_entity_id).state == "unavailable"
    assert (
        hass.states.get("light.living_room_tewke_switch_morning").state == "unavailable"
    )

    # Call async_turn_on on unavailable target to test missing target condition
    # This also covers the `if not super().available` checks in target and scene
    target1_entity = hass.data["light"].get_entity(target1_entity_id)
    assert target1_entity is not None
    await target1_entity.async_turn_on(brightness=128)
    mock_tap_with_lights.set_target.assert_not_called()

    scene1_entity = hass.data["light"].get_entity(
        "light.living_room_tewke_switch_morning"
    )
    assert scene1_entity is not None
    await scene1_entity.async_turn_on()
    mock_tap_with_lights.set_scene.assert_called_once_with(
        scene_id="scene1", state=True, brightness=100
    )

    # Also test `async_turn_on` on a target entity where `coordinator.data["targets"]` is missing the target
    # This covers `if target is None: return` in target.async_turn_on and `brightness` when target is None
    new_data = TewkeCoordinatorData(
        targets={},  # Target missing
        sensors=coordinator.data["sensors"],
        radar=coordinator.data["radar"],
        energy=coordinator.data["energy"],
        energy_override=coordinator.data["energy_override"],
        config=coordinator.data["config"],
    )
    coordinator.async_set_updated_data(new_data)

    assert target1_entity.brightness is None
    await target1_entity.async_turn_on()

    # Test coordinator failure makes entities unavailable (super().available == False)
    coordinator.last_update_success = False
    assert target1_entity.available is False
    assert scene1_entity.available is False


@pytest.mark.parametrize(
    ("exception", "expected_message"),
    [
        (
            PyTewkeInvalidWallDockError("Invalid wall dock"),
            "Attempted to set .* while not connected to Wall Dock",
        ),
        (
            PyTewkeInvalidRequestError("Invalid request"),
            "(?i)error .* tewke .*",
        ),
        (
            PyTewkeCoapError("Coap error", code=1),
            "(?i)error .* tewke .*",
        ),
    ],
)
async def test_light_errors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_tap_with_lights: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_message: str,
) -> None:
    """Test error handling when controlling lights."""
    mock_config_entry.add_to_hass(hass)

    entity_registry.async_get_or_create(
        LIGHT_DOMAIN,
        "tewke",
        "hw123_target_1",
        suggested_object_id="main_light",
        disabled_by=None,
        config_entry=mock_config_entry,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_tap_with_lights.set_scene.side_effect = exception
    mock_tap_with_lights.set_target.side_effect = exception

    with pytest.raises(HomeAssistantError, match=expected_message):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.living_room_tewke_switch_morning"},
            blocking=True,
        )

    with pytest.raises(HomeAssistantError, match=expected_message):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.main_light"},
            blocking=True,
        )

    with pytest.raises(HomeAssistantError, match=expected_message):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.main_light"},
            blocking=True,
        )
