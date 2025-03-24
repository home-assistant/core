"""Test ESPHome dates."""

from unittest.mock import call

from aioesphomeapi import APIClient, DateInfo, DateState

from homeassistant.components.date import (
    ATTR_DATE,
    DOMAIN as DATE_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant


async def test_generic_date_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a generic date entity."""
    entity_info = [
        DateInfo(
            object_id="mydate",
            key=1,
            name="my date",
            unique_id="my_date",
        )
    ]
    states = [DateState(key=1, year=2024, month=12, day=31)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("date.test_mydate")
    assert state is not None
    assert state.state == "2024-12-31"

    await hass.services.async_call(
        DATE_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "date.test_mydate", ATTR_DATE: "1999-01-01"},
        blocking=True,
    )
    mock_client.date_command.assert_has_calls([call(1, 1999, 1, 1)])
    mock_client.date_command.reset_mock()


async def test_generic_date_missing_state(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a generic date entity with missing state."""
    entity_info = [
        DateInfo(
            object_id="mydate",
            key=1,
            name="my date",
            unique_id="my_date",
        )
    ]
    states = [DateState(key=1, missing_state=True)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("date.test_mydate")
    assert state is not None
    assert state.state == STATE_UNKNOWN
