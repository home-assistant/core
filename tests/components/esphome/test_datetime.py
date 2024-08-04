"""Test ESPHome datetimes."""

from unittest.mock import call

from aioesphomeapi import APIClient, DateTimeInfo, DateTimeState

from homeassistant.components.datetime import (
    ATTR_DATETIME,
    DOMAIN as DATETIME_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant


async def test_generic_datetime_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a generic datetime entity."""
    entity_info = [
        DateTimeInfo(
            object_id="mydatetime",
            key=1,
            name="my datetime",
            unique_id="my_datetime",
        )
    ]
    states = [DateTimeState(key=1, epoch_seconds=1713270896)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("datetime.test_mydatetime")
    assert state is not None
    assert state.state == "2024-04-16T12:34:56+00:00"

    await hass.services.async_call(
        DATETIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "datetime.test_mydatetime",
            ATTR_DATETIME: "2000-01-01T01:23:45+00:00",
        },
        blocking=True,
    )
    mock_client.datetime_command.assert_has_calls([call(1, 946689825)])
    mock_client.datetime_command.reset_mock()


async def test_generic_datetime_missing_state(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a generic datetime entity with missing state."""
    entity_info = [
        DateTimeInfo(
            object_id="mydatetime",
            key=1,
            name="my datetime",
            unique_id="my_datetime",
        )
    ]
    states = [DateTimeState(key=1, missing_state=True)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("datetime.test_mydatetime")
    assert state is not None
    assert state.state == STATE_UNKNOWN
