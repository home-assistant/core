"""Tests for the Rachio switch platform."""

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


async def test_zone_services_update_state(
    hass: HomeAssistant,
    mock_rachio: MagicMock,
) -> None:
    """Test zone services optimistically update Home Assistant state."""
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


async def test_zone_start_failure_does_not_update_state(
    hass: HomeAssistant,
    mock_rachio: MagicMock,
) -> None:
    """Test a failed start command does not optimistically update state."""
    mock_rachio.zone.start.side_effect = RuntimeError

    with pytest.raises(RuntimeError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ZONE_ENTITY_ID},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_OFF)


async def test_zone_stop_failure_does_not_update_state(
    hass: HomeAssistant,
    mock_rachio: MagicMock,
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

    mock_rachio.device.stop_water.side_effect = RuntimeError

    with pytest.raises(RuntimeError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ZONE_ENTITY_ID},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_ON)
