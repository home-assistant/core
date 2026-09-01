"""Tests for the Imou integration."""

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def assert_reauth_flow(
    hass: HomeAssistant, entry: MockConfigEntry, *, started: bool
) -> None:
    """Assert whether a reauth flow is in progress for the config entry."""
    flows = hass.config_entries.flow.async_progress()
    if not started:
        assert flows == []
        return
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id
    assert flows[0]["step_id"] == "reauth_confirm"
