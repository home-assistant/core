"""Tests for number intents."""

import pytest

from homeassistant.components.number import (
    DOMAIN,
    SERVICE_SET_VALUE,
    intent as number_intent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from tests.common import async_mock_service


async def test_set_value(hass: HomeAssistant) -> None:
    """Test HassNumberSetValue intent."""
    await number_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_number"
    hass.states.async_set(entity_id, "50.0")
    calls = async_mock_service(hass, DOMAIN, SERVICE_SET_VALUE)

    response = await intent.async_handle(
        hass,
        "test",
        number_intent.INTENT_SET_VALUE,
        {"name": {"value": "test number"}, "value": {"value": 75.0}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": entity_id, "value": 75.0}


async def test_set_value_no_match(hass: HomeAssistant) -> None:
    """Test HassNumberSetValue intent with no matching entity."""
    await number_intent.async_setup_intents(hass)

    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            number_intent.INTENT_SET_VALUE,
            {"name": {"value": "nonexistent"}, "value": {"value": 10.0}},
        )
