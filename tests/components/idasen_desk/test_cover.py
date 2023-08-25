"""Test the IKEA Idasen Desk cover."""
from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
)
from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from . import init_integration, set_connection_switch


async def test_cover_available(
    hass: HomeAssistant,
    mock_desk_api: MagicMock,
) -> None:
    """Test cover available property."""
    entity_id = "cover.test"
    await init_integration(hass)
    await set_connection_switch(hass, True)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 60

    await set_connection_switch(hass, False)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("service", "service_data", "expected_state", "expected_position"),
    [
        (SERVICE_SET_COVER_POSITION, {ATTR_POSITION: 100}, STATE_OPEN, 100),
        (SERVICE_SET_COVER_POSITION, {ATTR_POSITION: 0}, STATE_CLOSED, 0),
        (SERVICE_OPEN_COVER, {}, STATE_OPEN, 100),
        (SERVICE_CLOSE_COVER, {}, STATE_CLOSED, 0),
        (SERVICE_STOP_COVER, {}, STATE_OPEN, 60),
    ],
)
async def test_cover_services(
    hass: HomeAssistant,
    mock_desk_api: MagicMock,
    service: str,
    service_data: dict[str, Any],
    expected_state: str,
    expected_position: int,
) -> None:
    """Test cover services."""
    entity_id = "cover.test"
    await init_integration(hass)
    await set_connection_switch(hass, True)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 60
    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {"entity_id": entity_id, **service_data},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == expected_state
    assert state.attributes[ATTR_CURRENT_POSITION] == expected_position
