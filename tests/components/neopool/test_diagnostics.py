"""Test the NeoPool diagnostics."""

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.neopool.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("mock_neopool_client")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry diagnostics output is stable and redacts host/port."""
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot(
        exclude=props(
            "created_at",
            "modified_at",
            "entry_id",
        )
    )


@pytest.mark.usefixtures("mock_neopool_client")
async def test_entry_diagnostics_exposes_only_exception_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """last_exception exposes the type only, never the raw message.

    The client embeds host:port in connection error messages, so the raw
    text must never be serialized into diagnostics.
    """
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator.last_exception = ConnectionError(
        "Modbus client connection failed to 192.0.2.15:502"
    )
    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert result["coordinator"]["last_exception"] == "ConnectionError"
    assert "192.0.2.15" not in str(result)
