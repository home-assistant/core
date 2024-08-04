"""Tests for the Nextcloud init."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration
from .const import NC_DATA, VALID_CONFIG


async def test_async_setup_entry(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test a successful setup entry."""
    entry = await init_integration(hass, VALID_CONFIG, NC_DATA)

    assert entry.state == ConfigEntryState.LOADED

    states = hass.states.async_all()
    assert len(states) == 44

    for state in states:
        assert state.state == snapshot(name=f"{state.entity_id}_state")
        assert state.attributes == snapshot(name=f"{state.entity_id}_attributes")
