"""Test setting up Local vision."""

from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry
from tarsius import BackendError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Load the model on setup and unload cleanly."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert hass.states.get("ai_task.local_vision") is not None

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_model_unavailable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Fail for good when the bundled model cannot be loaded."""
    assert await async_setup_component(hass, "homeassistant", {})
    with patch(
        "homeassistant.components.local_vision.NcnnBackend",
        side_effect=BackendError("missing"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == "The image model could not be loaded: missing"
