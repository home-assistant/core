"""Test Roborock Select platform."""
from unittest.mock import patch

import pytest

from homeassistant.const import SERVICE_SELECT_OPTION, Platform
from homeassistant.core import HomeAssistant

from .common import setup_platform


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        ("select.roborock_s7_maxv_mop_mode", "deep"),
        ("select.roborock_s7_maxv_mop_intensity", "mild"),
    ],
)
async def test_update_success(
    hass: HomeAssistant, bypass_api_fixture, entity_id, value
) -> None:
    """Test allowed changing values for select entities."""

    # Setup component
    assert await setup_platform(hass, [Platform.SELECT])
    # Test
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.send_message"
    ) as mock_send_message:
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            service_data={"option": value},
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert mock_send_message.assert_called_once
