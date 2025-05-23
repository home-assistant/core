"""Test ESPHome texts."""

from unittest.mock import call

from aioesphomeapi import APIClient, TextInfo, TextMode as ESPHomeTextMode, TextState

from homeassistant.components.text import (
    ATTR_VALUE,
    DOMAIN as TEXT_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
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
            unique_id="my_text",
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
    state = hass.states.get("text.test_mytext")
    assert state is not None
    assert state.state == "hello world"

    await hass.services.async_call(
        TEXT_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "text.test_mytext", ATTR_VALUE: "goodbye"},
        blocking=True,
    )
    mock_client.text_command.assert_has_calls([call(1, "goodbye")])
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
            unique_id="my_text",
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
    state = hass.states.get("text.test_mytext")
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
            unique_id="my_text",
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
    state = hass.states.get("text.test_mytext")
    assert state is not None
    assert state.state == STATE_UNKNOWN
