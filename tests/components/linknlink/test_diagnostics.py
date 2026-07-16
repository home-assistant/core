"""Tests for LinknLink diagnostics."""

from dataclasses import replace
from unittest.mock import AsyncMock

from homeassistant.components.linknlink.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import POSITION_STATE

from tests.common import MockConfigEntry


async def test_diagnostics_while_setup_is_pending(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics before the coordinator has been assigned."""
    mock_config_entry.add_to_hass(hass)

    result = await async_get_config_entry_diagnostics(
        hass,
        mock_config_entry,  # type: ignore[arg-type]
    )

    assert result["config_entry"]["data"]["host"] == "**REDACTED**"
    assert result["device"] is None
    assert result["position_subscription"] is None
    assert result["environment_state"] is None
    assert result["environment_available"] is False
    assert result["last_update_success"] is False


async def test_diagnostics_are_redacted(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that diagnostics do not expose device identifiers or private data."""
    await setup_integration(hass, mock_config_entry)
    mock_config_entry.runtime_data.position_state = replace(
        POSITION_STATE,
        last_error="timeout waiting for 192.168.3.159:80",
    )

    result = await async_get_config_entry_diagnostics(
        hass,
        mock_config_entry,  # type: ignore[arg-type]
    )

    assert result["config_entry"]["data"]["host"] == "**REDACTED**"
    assert result["config_entry"]["data"]["mac"] == "**REDACTED**"
    assert result["config_entry"]["unique_id"] == "**REDACTED**"
    assert result["device"]["ip"] == "**REDACTED**"
    assert result["device"]["mac"] == "**REDACTED**"
    position = result["position_subscription"]["latest_update"]
    assert position["source_ip"] == "**REDACTED**"
    assert position["targets"] == "**REDACTED**"
    assert result["position_subscription"]["last_error"] == "**REDACTED**"
    assert result["environment_state"]["device_id"] == "**REDACTED**"
    assert result["environment_state"]["values"]["temperature"] == 23.5
    assert result["environment_available"] is True
