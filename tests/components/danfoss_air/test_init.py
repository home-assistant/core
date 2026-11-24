"""Tests for the Danfoss Air integration setup and polling."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from . import setup_integration


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Move past the update throttle and update every entity one at a time."""
    freezer.tick(timedelta(seconds=61))
    for entity_id in hass.states.async_entity_ids():
        await async_update_entity(hass, entity_id)


def _unavailable(hass: HomeAssistant) -> list[str]:
    """Return the entities that are unavailable."""
    return [
        state.entity_id
        for state in hass.states.async_all()
        if state.state == STATE_UNAVAILABLE
    ]


async def test_unavailable_when_connection_lost(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_danfoss_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test entities go unavailable when the CCM is unreachable, and recover."""
    await setup_integration(hass)
    await _poll(hass, freezer)
    entity_ids = hass.states.async_entity_ids()
    assert entity_ids
    assert _unavailable(hass) == []

    read_values = mock_danfoss_client.command.side_effect
    mock_danfoss_client.command.side_effect = OSError("No route to host")

    await _poll(hass, freezer)
    assert sorted(_unavailable(hass)) == sorted(entity_ids)
    assert "Lost connection to Danfoss Air CCM module" in caplog.text

    # Only the first failed poll is logged.
    caplog.clear()
    await _poll(hass, freezer)
    assert sorted(_unavailable(hass)) == sorted(entity_ids)
    assert "Lost connection" not in caplog.text

    mock_danfoss_client.command.side_effect = read_values

    await _poll(hass, freezer)
    assert _unavailable(hass) == []
    assert "Connection to Danfoss Air CCM module restored" in caplog.text
