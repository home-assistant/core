"""Test Roborock Number platform."""

from unittest.mock import Mock

import pytest
from roborock.exceptions import RoborockTimeout

from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.NUMBER]


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        ("number.roborock_s7_maxv_volume", 3.0),
    ],
)
async def test_update_success(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    entity_id: str,
    value: float,
    mock_send_message: Mock,
) -> None:
    """Test allowed changing values for number entities."""
    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get(entity_id) is not None
    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: value},
        blocking=True,
        target={"entity_id": entity_id},
    )
    assert mock_send_message.assert_called_once


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        ("number.roborock_s7_maxv_volume", 3.0),
    ],
)
@pytest.mark.parametrize("send_message_side_effect", [RoborockTimeout])
async def test_update_failed(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    entity_id: str,
    value: float,
    mock_send_message: Mock,
) -> None:
    """Test allowed changing values for number entities."""
    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get(entity_id) is not None
    with pytest.raises(HomeAssistantError, match="Failed to update Roborock options"):
        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            service_data={ATTR_VALUE: value},
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert mock_send_message.assert_called_once
