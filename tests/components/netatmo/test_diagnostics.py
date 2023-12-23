"""Test the Netatmo diagnostics."""
from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion
from syrupy.filters import paths

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import fake_post_request

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    config_entry,
) -> None:
    """Test config entry diagnostics."""
    with patch(
        "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth",
    ) as mock_auth, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.netatmo.webhook_generate_url"
    ):
        mock_auth.return_value.async_post_api_request.side_effect = fake_post_request
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        assert await async_setup_component(hass, "netatmo", {})

    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    ) == snapshot(exclude=paths("info.data.token.expires_at", "info.entry_id"))
