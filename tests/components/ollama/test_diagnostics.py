"""Test Ollama diagnostics."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    "has_token",
    [
        pytest.param(True, id="api_key"),
        pytest.param(False, id="no_api_key"),
    ],
)
@pytest.mark.usefixtures("mock_init_component")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry_with_assist: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    assert (
        await get_diagnostics_for_config_entry(
            hass, hass_client, mock_config_entry_with_assist
        )
        == snapshot
    )
