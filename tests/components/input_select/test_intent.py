"""Tests for input_select intents."""

import pytest

from homeassistant.components.input_select import DOMAIN, intent as input_select_intent
from homeassistant.components.select import ATTR_OPTIONS, SERVICE_SELECT_OPTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from tests.common import async_mock_service


async def test_select_option(hass: HomeAssistant) -> None:
    """Test HassInputSelectSelectOption intent."""
    await input_select_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_input_select"
    hass.states.async_set(
        entity_id, "red", {ATTR_OPTIONS: ["red", "green", "blue"]}
    )
    calls = async_mock_service(hass, DOMAIN, SERVICE_SELECT_OPTION)

    response = await intent.async_handle(
        hass,
        "test",
        input_select_intent.INTENT_SELECT_OPTION,
        {"name": {"value": "test input select"}, "option": {"value": "green"}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": entity_id, "option": "green"}


async def test_select_option_invalid(hass: HomeAssistant) -> None:
    """Test HassInputSelectSelectOption intent with an invalid option."""
    await input_select_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_input_select"
    hass.states.async_set(
        entity_id, "red", {ATTR_OPTIONS: ["red", "green", "blue"]}
    )

    with pytest.raises(intent.IntentHandleError) as exc_info:
        await intent.async_handle(
            hass,
            "test",
            input_select_intent.INTENT_SELECT_OPTION,
            {"name": {"value": "test input select"}, "option": {"value": "yellow"}},
        )

    assert "yellow" in str(exc_info.value)
    assert "red" in str(exc_info.value)


async def test_select_option_no_match(hass: HomeAssistant) -> None:
    """Test HassInputSelectSelectOption intent with no matching entity."""
    await input_select_intent.async_setup_intents(hass)

    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            input_select_intent.INTENT_SELECT_OPTION,
            {"name": {"value": "nonexistent"}, "option": {"value": "red"}},
        )
