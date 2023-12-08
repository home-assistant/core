"""Provide tests for mysensors text platform."""
from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock, call

from mysensors.sensor import Sensor
import pytest

from homeassistant.components.text import (
    ATTR_VALUE,
    DOMAIN as TEXT_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_BATTERY_LEVEL, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


async def test_text_node(
    hass: HomeAssistant,
    text_node: Sensor,
    receive_message: Callable[[str], None],
    transport_write: MagicMock,
) -> None:
    """Test a text node."""
    entity_id = "text.text_node_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "test"
    assert state.attributes[ATTR_BATTERY_LEVEL] == 0

    await hass.services.async_call(
        TEXT_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: "Hello World"},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;47;Hello World\n")

    receive_message("1;1;1;0;47;Hello World\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "Hello World"

    transport_write.reset_mock()

    value = "12345678123456781234567812"

    with pytest.raises(ValueError) as err:
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
            blocking=True,
        )

    assert str(err.value) == (
        f"Value {value} for text.text_node_1_1 is too long (maximum length 25)"
    )
