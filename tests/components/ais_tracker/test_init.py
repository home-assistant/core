"""Tests for AIS tracker config flow."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.ais_tracker.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import MOCK_USER_DATA

from tests.common import MockConfigEntry


async def test_init(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test init of AIS tracker component."""
    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.ais_tracker.coordinator.AisTrackerCoordinator.async_setup"
    ) as mock_setup_coordinator:
        await hass.config_entries.async_setup(mock_config.entry_id)

    assert mock_setup_coordinator.called

    states = hass.states.async_all()
    assert len(states) == 8

    for state in states:
        assert state == snapshot(name=state.entity_id)
