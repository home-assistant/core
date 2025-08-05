"""Test Roborock Switch platform."""

from unittest.mock import Mock

import pytest
import roborock

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.SWITCH]


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("switch.roborock_s7_maxv_dock_child_lock"),
        ("switch.roborock_s7_maxv_dock_status_indicator_light"),
        ("switch.roborock_s7_maxv_do_not_disturb"),
    ],
)
async def test_update_success(
    hass: HomeAssistant,
    mock_send_message: Mock,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    entity_id: str,
) -> None:
    """Test turning switch entities on and off."""
    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get(entity_id) is not None
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_ON,
        service_data=None,
        blocking=True,
        target={"entity_id": entity_id},
    )
    assert mock_send_message.assert_called_once
    mock_send_message.reset_mock()
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_OFF,
        service_data=None,
        blocking=True,
        target={"entity_id": entity_id},
    )
    assert mock_send_message.assert_called_once


@pytest.mark.parametrize(
    ("entity_id", "service"),
    [
        ("switch.roborock_s7_maxv_dock_status_indicator_light", SERVICE_TURN_ON),
        ("switch.roborock_s7_maxv_dock_status_indicator_light", SERVICE_TURN_OFF),
    ],
)
@pytest.mark.parametrize(
    "send_message_side_effect", [roborock.exceptions.RoborockTimeout]
)
async def test_update_failed(
    hass: HomeAssistant,
    mock_send_message: Mock,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    entity_id: str,
    service: str,
) -> None:
    """Test a failure while updating a switch."""
    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get(entity_id) is not None
    with (
        pytest.raises(HomeAssistantError, match="Failed to update Roborock options"),
    ):
        await hass.services.async_call(
            "switch",
            service,
            service_data=None,
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert mock_send_message.assert_called_once
