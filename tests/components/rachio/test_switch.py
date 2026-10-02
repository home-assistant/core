"""Tests for the Rachio switch platform."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

CONTROLLER_ID = "controller-id"
ZONE_ID = "zone-id"
ZONE_ENTITY_ID = "switch.test_controller_test_zone"

MOCK_CONTROLLER = {
    "id": CONTROLLER_ID,
    "name": "Test Controller",
    "serialNumber": "serial-number",
    "macAddress": "00:9D:6B:00:00:01",
    "model": "GENERATION3",
    "zones": [
        {
            "id": ZONE_ID,
            "name": "Test Zone",
            "zoneNumber": 1,
            "enabled": True,
        }
    ],
    "scheduleRules": [],
    "flexScheduleRules": [],
}

pytestmark = [
    pytest.mark.parametrize("mock_rachio", [[MOCK_CONTROLLER]], indirect=True),
    pytest.mark.parametrize("init_integration", [Platform.SWITCH], indirect=True),
    pytest.mark.usefixtures("init_integration"),
]


@pytest.mark.parametrize(
    "success_status",
    [
        pytest.param(200, id="ok"),
        pytest.param(204, id="no-content"),
    ],
)
async def test_zone_services_update_state(
    hass: HomeAssistant,
    mock_rachio: MagicMock,
    success_status: int,
) -> None:
    """Test zone services optimistically update Home Assistant state."""
    mock_rachio.device.stop_water.return_value = ({"status": success_status}, {})
    mock_rachio.zone.start.return_value = ({"status": success_status}, {})

    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_OFF)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ZONE_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_ON)
    mock_rachio.device.stop_water.assert_called_once_with(CONTROLLER_ID)
    mock_rachio.zone.start.assert_called_once_with(ZONE_ID, 600)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ZONE_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_OFF)
    assert mock_rachio.device.stop_water.call_count == 2


@pytest.mark.parametrize(
    ("response", "side_effect", "expected_exception"),
    [
        pytest.param(
            ({"status": 500}, {}),
            None,
            HomeAssistantError,
            id="error-response",
        ),
        pytest.param(None, RuntimeError, RuntimeError, id="exception"),
    ],
)
async def test_zone_start_failure_does_not_update_state(
    hass: HomeAssistant,
    mock_rachio: MagicMock,
    response: tuple[dict[str, int], dict[str, Any]] | None,
    side_effect: type[Exception] | None,
    expected_exception: type[Exception],
) -> None:
    """Test a failed start command does not optimistically update state."""
    mock_rachio.zone.start.return_value = response
    mock_rachio.zone.start.side_effect = side_effect

    with pytest.raises(expected_exception):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ZONE_ENTITY_ID},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_OFF)


@pytest.mark.parametrize(
    ("response", "side_effect", "expected_exception"),
    [
        pytest.param(
            ({"status": 500}, {}),
            None,
            HomeAssistantError,
            id="error-response",
        ),
        pytest.param(None, RuntimeError, RuntimeError, id="exception"),
    ],
)
async def test_zone_stop_failure_does_not_update_state(
    hass: HomeAssistant,
    mock_rachio: MagicMock,
    response: tuple[dict[str, int], dict[str, Any]] | None,
    side_effect: type[Exception] | None,
    expected_exception: type[Exception],
) -> None:
    """Test a failed stop command does not optimistically update state."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ZONE_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_ON)

    mock_rachio.device.stop_water.return_value = response
    mock_rachio.device.stop_water.side_effect = side_effect

    with pytest.raises(expected_exception):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ZONE_ENTITY_ID},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_ON)
