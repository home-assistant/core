"""Test diagnostics for madVR Envy integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_HOST

from homeassistant.components.madvr.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_redacts_sensitive_data(hass, mock_config_entry, mock_envy_client):
    """Test diagnostics redaction behavior."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.madvr.MadvrEnvyClient", return_value=mock_envy_client),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert diagnostics["entry"]["data"][CONF_HOST] == "**REDACTED**"
    assert diagnostics["runtime"]["host"] == "**REDACTED**"
    assert diagnostics["runtime"]["state"]["mac_address"] == "**REDACTED**"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
