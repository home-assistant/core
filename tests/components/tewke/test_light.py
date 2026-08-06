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
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def mock_tap_with_lights(mock_tap):
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
    mock_tap_with_lights,
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

    # Turn on target1
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.main_light", ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    mock_tap_with_lights.set_target.assert_called_with(target=1, brightness=100)


@pytest.mark.parametrize(
    ("exception", "expected_message"),
    [
        (
            PyTewkeInvalidWallDockError("Invalid wall dock"),
            "Attempted to set .* while not connected to Wall Dock",
        ),
        (
            PyTewkeInvalidRequestError("Invalid request"),
            "Internal error .* Tewke .*",
        ),
        (
            PyTewkeCoapError("Coap error", code=1),
            "Error .* Tewke .*",
        ),
    ],
)
async def test_light_errors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_tap_with_lights,
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
