"""Test Prosegur diagnostics."""
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration,
    mock_install,
) -> None:
    """Test generating diagnostics for a config entry."""

    with patch(
        "pyprosegur.installation.Installation.retrieve", return_value=mock_install
    ):
        diag = await get_diagnostics_for_config_entry(
            hass, hass_client, init_integration
        )

        assert diag == {
            "installation": {"contract": "1234abcd"},
            "activity": {"event": "armed"},
        }
