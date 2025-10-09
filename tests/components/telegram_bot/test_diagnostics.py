"""Tests for Telegram bot diagnostics."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.telegram_bot.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    webhook_platform,
    mock_external_calls: None,
    mock_generate_secret_token,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    assert diagnostics == snapshot
