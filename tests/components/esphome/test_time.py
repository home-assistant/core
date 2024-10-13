"""Test ESPHome times."""

from unittest.mock import call

from aioesphomeapi import APIClient, TimeInfo, TimeState

from homeassistant.components.time import (
    ATTR_TIME,
    DOMAIN as TIME_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant


async def test_generic_time_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a generic time entity."""
    entity_info = [
        TimeInfo(
            object_id="mytime",
            key=1,
            name="my time",
            unique_id="my_time",
        )
    ]
    states = [TimeState(key=1, hour=12, minute=34, second=56)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("time.test_mytime")
    assert state is not None
    assert state.state == "12:34:56"

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "time.test_mytime", ATTR_TIME: "01:23:45"},
        blocking=True,
    )
    mock_client.time_command.assert_has_calls([call(1, 1, 23, 45)])
    mock_client.time_command.reset_mock()


async def test_generic_time_missing_state(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a generic time entity with missing state."""
    entity_info = [
        TimeInfo(
            object_id="mytime",
            key=1,
            name="my time",
            unique_id="my_time",
        )
    ]
    states = [TimeState(key=1, missing_state=True)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("time.test_mytime")
    assert state is not None
    assert state.state == STATE_UNKNOWN
