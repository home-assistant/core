"""Test Roborock Button platform."""

from unittest.mock import patch

import pytest
import roborock

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


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
