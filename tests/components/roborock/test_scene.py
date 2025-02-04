"""Test Roborock Scene platform."""

from unittest.mock import ANY, patch

import pytest
from roborock import RoborockException

from homeassistant.const import SERVICE_TURN_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.SCENE]


@pytest.mark.parametrize(
    ("entity_id", "scene_id"),
    [
        ("scene.roborock_s7_maxv_sc1", 12),
        ("scene.roborock_s7_maxv_sc2", 24),
    ],
)
@pytest.mark.freeze_time("2023-10-30 08:50:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_execute_success(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    entity_id: str,
    scene_id: int,
) -> None:
    """Test activating the scene entities."""
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.execute_scene"
    ) as mock_execute_scene:
        await hass.services.async_call(
            "scene",
            SERVICE_TURN_ON,
            blocking=True,
            target={"entity_id": entity_id},
        )
    mock_execute_scene.assert_called_once_with(ANY, scene_id)
    assert hass.states.get(entity_id).state == "2023-10-30T08:50:00+00:00"


@pytest.mark.parametrize(
    ("entity_id", "scene_id"),
    [
        ("scene.roborock_s7_maxv_sc1", 12),
    ],
)
@pytest.mark.freeze_time("2023-10-30 08:50:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_execute_failure(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    entity_id: str,
    scene_id: int,
) -> None:
    """Test failure while activating the scene entity."""
    with (
        patch(
            "homeassistant.components.roborock.RoborockApiClient.execute_scene",
            side_effect=RoborockException,
        ) as mock_execute_scene,
        pytest.raises(HomeAssistantError, match="Error while calling execute_scene"),
    ):
        await hass.services.async_call(
            "scene",
            SERVICE_TURN_ON,
            blocking=True,
            target={"entity_id": entity_id},
        )
    mock_execute_scene.assert_called_once_with(ANY, scene_id)
    assert hass.states.get(entity_id).state == "2023-10-30T08:50:00+00:00"
