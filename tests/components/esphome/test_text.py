"""Test ESPHome texts."""

from unittest.mock import call

from aioesphomeapi import APIClient, TextInfo, TextMode as ESPHomeTextMode, TextState

from homeassistant.components.text import (
    DOMAIN as TEXT_DOMAIN,
    TextService,
    TextServiceArgument,
)
from homeassistant.const import STATE_UNKNOWN, TargetKey
from homeassistant.core import HomeAssistant

from .conftest import MockGenericDeviceEntryType


async def test_generic_text_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic text entity."""
    entity_info = [
        TextInfo(
            object_id="mytext",
            key=1,
            name="my text",
            max_length=100,
            min_length=0,
            pattern=None,
            mode=ESPHomeTextMode.TEXT,
        )
    ]
    states = [TextState(key=1, state="hello world")]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("text.test_my_text")
    assert state is not None
    assert state.state == "hello world"

    await hass.services.async_call(
        TEXT_DOMAIN,
        TextService.SET_VALUE,
        {
            TargetKey.ENTITY_ID: "text.test_my_text",
            TextServiceArgument.VALUE: "goodbye",
        },
        blocking=True,
    )
    mock_client.text_command.assert_has_calls([call(1, "goodbye", device_id=0)])
    mock_client.text_command.reset_mock()


async def test_generic_text_entity_no_state(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic text entity that has no state."""
    entity_info = [
        TextInfo(
            object_id="mytext",
            key=1,
            name="my text",
            max_length=100,
            min_length=0,
            pattern=None,
            mode=ESPHomeTextMode.TEXT,
        )
    ]
    states = []
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("text.test_my_text")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_generic_text_entity_missing_state(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic text entity that has no state."""
    entity_info = [
        TextInfo(
            object_id="mytext",
            key=1,
            name="my text",
            max_length=100,
            min_length=0,
            pattern=None,
            mode=ESPHomeTextMode.TEXT,
        )
    ]
    states = [TextState(key=1, state="", missing_state=True)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("text.test_my_text")
    assert state is not None
    assert state.state == STATE_UNKNOWN
