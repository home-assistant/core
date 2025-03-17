"""Tests of the events of the balboa integration."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import snapshot_platform

ENTITY_EVENT = "event.fakespa_fault"
FAULT_DATE = "fault_date"


async def test_events(
    hass: HomeAssistant,
    client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test spa events."""
    with patch("homeassistant.components.balboa.PLATFORMS", [Platform.EVENT]):
        entry = await init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_event(hass: HomeAssistant, client: MagicMock) -> None:
    """Test spa fault event."""
    await init_integration(hass)

    # check the state is unknown
    state = hass.states.get(ENTITY_EVENT)
    assert state.state == STATE_UNKNOWN

    # set a fault
    client.fault = MagicMock(
        fault_datetime=datetime(2025, 2, 15, 13, 0), message_code=16
    )
    client.emit("")
    await hass.async_block_till_done()

    # check new state is what we expect
    state = hass.states.get(ENTITY_EVENT)
    assert state.attributes[ATTR_EVENT_TYPE] == "low_flow"
    assert state.attributes[FAULT_DATE] == "2025-02-15T13:00:00"
    assert state.attributes["code"] == 16

    # set fault to None
    client.fault = None
    client.emit("")
    await hass.async_block_till_done()

    # validate state remains unchanged
    state = hass.states.get(ENTITY_EVENT)
    assert state.attributes[ATTR_EVENT_TYPE] == "low_flow"
    assert state.attributes[FAULT_DATE] == "2025-02-15T13:00:00"
    assert state.attributes["code"] == 16

    # set fault to an unknown one
    client.fault = MagicMock(
        fault_datetime=datetime(2025, 2, 15, 14, 0), message_code=-1
    )
    # validate a ValueError is raises
    with pytest.raises(ValueError):
        client.emit("")
    await hass.async_block_till_done()

    # validate state remains unchanged
    state = hass.states.get(ENTITY_EVENT)
    assert state.attributes[ATTR_EVENT_TYPE] == "low_flow"
    assert state.attributes[FAULT_DATE] == "2025-02-15T13:00:00"
    assert state.attributes["code"] == 16
