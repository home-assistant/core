"""Test Roborock Button platform."""

from unittest.mock import ANY, patch

import pytest
import roborock
from roborock import RoborockException

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


@pytest.fixture
def bypass_api_client_get_scenes_fixture(bypass_api_fixture) -> None:
    """Fixture to raise when getting scenes."""
    with (
        patch(
            "homeassistant.components.roborock.RoborockApiClient.get_scenes",
            side_effect=RoborockException(),
        ),
    ):
        yield


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.BUTTON]


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("button.roborock_s7_maxv_reset_sensor_consumable"),
        ("button.roborock_s7_maxv_reset_air_filter_consumable"),
        ("button.roborock_s7_maxv_reset_side_brush_consumable"),
        ("button.roborock_s7_maxv_reset_main_brush_consumable"),
    ],
)
@pytest.mark.freeze_time("2023-10-30 08:50:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update_success(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    entity_id: str,
) -> None:
    """Test pressing the button entities."""
    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get(entity_id).state == "unknown"
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.send_message"
    ) as mock_send_message:
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert mock_send_message.assert_called_once
    assert hass.states.get(entity_id).state == "2023-10-30T08:50:00+00:00"


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("button.roborock_s7_maxv_reset_air_filter_consumable"),
    ],
)
@pytest.mark.freeze_time("2023-10-30 08:50:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update_failure(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    entity_id: str,
) -> None:
    """Test failure while pressing the button entity."""
    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get(entity_id).state == "unknown"
    with (
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.send_message",
            side_effect=roborock.exceptions.RoborockTimeout,
        ) as mock_send_message,
        pytest.raises(HomeAssistantError, match="Error while calling RESET_CONSUMABLE"),
    ):
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert mock_send_message.assert_called_once
    assert hass.states.get(entity_id).state == "2023-10-30T08:50:00+00:00"


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("button.roborock_s7_maxv_sc1"),
        ("button.roborock_s7_maxv_sc2"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_get_button_routines_failure(
    hass: HomeAssistant,
    bypass_api_client_get_scenes_fixture,
    setup_entry: MockConfigEntry,
    entity_id: str,
) -> None:
    """Test that if routine retrieval fails, no entity is being created."""
    # Ensure that the entity does not exist
    assert hass.states.get(entity_id) is None


@pytest.mark.parametrize(
    ("entity_id", "routine_id"),
    [
        ("button.roborock_s7_maxv_sc1", 12),
        ("button.roborock_s7_maxv_sc2", 24),
    ],
)
@pytest.mark.freeze_time("2023-10-30 08:50:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_press_routine_button_success(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    entity_id: str,
    routine_id: int,
) -> None:
    """Test pressing the button entities."""
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.execute_scene"
    ) as mock_execute_scene:
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            blocking=True,
            target={"entity_id": entity_id},
        )
    mock_execute_scene.assert_called_once_with(ANY, routine_id)
    assert hass.states.get(entity_id).state == "2023-10-30T08:50:00+00:00"


@pytest.mark.parametrize(
    ("entity_id", "routine_id"),
    [
        ("button.roborock_s7_maxv_sc1", 12),
    ],
)
@pytest.mark.freeze_time("2023-10-30 08:50:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_press_routine_button_failure(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    entity_id: str,
    routine_id: int,
) -> None:
    """Test failure while pressing the button entity."""
    with (
        patch(
            "homeassistant.components.roborock.RoborockApiClient.execute_scene",
            side_effect=RoborockException,
        ) as mock_execute_scene,
        pytest.raises(HomeAssistantError, match="Error while calling execute_scene"),
    ):
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            blocking=True,
            target={"entity_id": entity_id},
        )
    mock_execute_scene.assert_called_once_with(ANY, routine_id)
    assert hass.states.get(entity_id).state == "2023-10-30T08:50:00+00:00"
