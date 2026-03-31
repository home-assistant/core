"""Tests for select intents."""

import pytest

from homeassistant.components.select import (
    ATTR_OPTIONS,
    DOMAIN,
    SERVICE_SELECT_OPTION,
    intent as select_intent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from tests.common import async_mock_service


async def test_select_option(hass: HomeAssistant) -> None:
    """Test HassSelectSelectOption intent."""
    await select_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_select"
    hass.states.async_set(
        entity_id, "option1", {ATTR_OPTIONS: ["option1", "option2", "option3"]}
    )
    calls = async_mock_service(hass, DOMAIN, SERVICE_SELECT_OPTION)

    response = await intent.async_handle(
        hass,
        "test",
        select_intent.INTENT_SELECT_OPTION,
        {"name": {"value": "test select"}, "option": {"value": "option2"}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": entity_id, "option": "option2"}


async def test_select_option_invalid(hass: HomeAssistant) -> None:
    """Test HassSelectSelectOption intent with an invalid option."""
    await select_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_select"
    hass.states.async_set(
        entity_id, "option1", {ATTR_OPTIONS: ["option1", "option2"]}
    )

    with pytest.raises(intent.IntentHandleError) as exc_info:
        await intent.async_handle(
            hass,
            "test",
            select_intent.INTENT_SELECT_OPTION,
            {"name": {"value": "test select"}, "option": {"value": "bad_option"}},
        )

    assert "bad_option" in str(exc_info.value)
    assert "option1" in str(exc_info.value)
    assert "option2" in str(exc_info.value)


async def test_select_option_no_match(hass: HomeAssistant) -> None:
    """Test HassSelectSelectOption intent with no matching entity."""
    await select_intent.async_setup_intents(hass)

    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            select_intent.INTENT_SELECT_OPTION,
            {"name": {"value": "nonexistent"}, "option": {"value": "option1"}},
        )
