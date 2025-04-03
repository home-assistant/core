"""Tests for Bosch Alarm component."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import call_observable, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch("homeassistant.components.bosch_alarm.PLATFORMS", [Platform.SWITCH]):
        yield


async def test_update_switch_device(
    hass: HomeAssistant,
    mock_panel: AsyncMock,
    output: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that alarm panel state changes after arming the panel."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "switch.output_a"
    assert hass.states.get(entity_id).state == STATE_OFF
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    output.is_active.return_value = True
    await call_observable(hass, output.status_observer)
    assert hass.states.get(entity_id).state == STATE_ON


async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_panel: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch state."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
