"""Test ESPHome selects."""


from unittest.mock import call

from aioesphomeapi import APIClient, SelectInfo, SelectState

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


async def test_pipeline_selector(
    hass: HomeAssistant,
    mock_voice_assistant_v1_entry,
) -> None:
    """Test assist pipeline selector."""

    state = hass.states.get("select.test_assist_pipeline")
    assert state is not None
    assert state.state == "preferred"


async def test_vad_sensitivity_select(
    hass: HomeAssistant,
    mock_voice_assistant_v1_entry,
) -> None:
    """Test VAD sensitivity select.

    Functionality is tested in assist_pipeline/test_select.py.
    This test is only to ensure it is set up.
    """
    state = hass.states.get("select.test_finished_speaking_detection")
    assert state is not None
    assert state.state == "default"


async def test_select_generic_entity(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic select entity."""
    entity_info = [
        SelectInfo(
            object_id="myselect",
            key=1,
            name="my select",
            unique_id="my_select",
            options=["a", "b"],
        )
    ]
    states = [SelectState(key=1, state="a")]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("select.test_myselect")
    assert state is not None
    assert state.state == "a"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.test_myselect", ATTR_OPTION: "b"},
        blocking=True,
    )
    mock_client.select_command.assert_has_calls([call(1, "b")])
