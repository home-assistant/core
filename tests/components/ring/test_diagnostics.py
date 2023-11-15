"""Test Ring diagnostics."""

from unittest.mock import Mock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_added_config_entry: MockConfigEntry,
    mock_ring: Mock,
) -> None:
    """Test Ring diagnostics."""
    mock_ring.devices_data = {"doorbots": {"1234": {"id": "foo", "safe": "bar"}}}
    diag = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_added_config_entry
    )
    assert diag == {"device_data": [{"id": "**REDACTED**", "safe": "bar"}]}
