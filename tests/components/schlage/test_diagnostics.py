"""Test Schlage diagnostics."""

from unittest.mock import Mock

from homeassistant.core import HomeAssistant

from . import MockSchlageConfigEntry

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_added_config_entry: MockSchlageConfigEntry,
    mock_lock: Mock,
) -> None:
    """Test Schlage diagnostics."""
    mock_lock.get_diagnostics.return_value = {"foo": "bar"}
    diag = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_added_config_entry
    )
    assert diag == {"locks": [{"foo": "bar"}]}
