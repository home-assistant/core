"""Test Prosegur diagnostics."""

from unittest.mock import AsyncMock, patch

from .common import setup_platform

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(hass, hass_client, mock_prosegur_auth):
    """Test generating diagnostics for a config entry."""

    install = AsyncMock()
    install.data = {"contract": "123"}
    install.activity = AsyncMock(return_value={"event": "armed"})

    with patch("pyprosegur.installation.Installation.retrieve", return_value=install):

        await setup_platform(hass)

        await hass.async_block_till_done()

        entry = hass.config_entries.async_entries("prosegur")[0]

        diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

        assert diag == {
            "installation": {"contract": "123"},
            "activity": {"event": "armed"},
        }
