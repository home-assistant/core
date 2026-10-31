"""Tests for Telegram bot diagnostics."""

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.telegram_bot.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    webhook_bot,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    assert diagnostics == snapshot
