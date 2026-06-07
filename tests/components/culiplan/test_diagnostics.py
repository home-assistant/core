"""Tests for diagnostics redaction."""

from homeassistant.components.culiplan.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_diagnostics_redacts_tokens_and_ids(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Tokens and identifiers are absent from the diagnostics payload."""
    diag = await async_get_config_entry_diagnostics(hass, setup_integration)

    rendered = repr(diag)
    assert "test-access-token" not in rendered
    assert "user-123" not in rendered
    assert "token_age_seconds" in diag
    assert "coordinator" in diag
    assert "last_update_success" in diag["coordinator"]


async def test_diagnostics_with_no_token_issued_at(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Without an ``issued_at`` field, token_age_seconds is None."""
    # Mutate the entry data to drop issued_at.
    hass.config_entries.async_update_entry(
        setup_integration,
        data={
            "auth_implementation": "culiplan",
            "token": {"access_token": "x", "refresh_token": "y"},
        },
    )
    await hass.async_block_till_done()
    diag = await async_get_config_entry_diagnostics(hass, setup_integration)
    assert diag["token_age_seconds"] is None
