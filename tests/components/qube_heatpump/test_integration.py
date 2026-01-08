"""Integration tests for the Qube Heat Pump component."""

import socket
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.qube_heatpump.const import CONF_HOST, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_setup_with_entities(
    hass: HomeAssistant, mock_modbus_client: MagicMock
) -> None:
    """Test full setup including entity creation and state update."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10"},
        title="Qube Heat Pump",
    )
    entry.add_to_hass(hass)

    # Use the global mock_modbus_client fixture instead of re-patching
    mock_client = mock_modbus_client.return_value

    # Mock reading registers.
    async def mock_read(*args: Any, **kwargs: Any) -> Any:
        mock_res = MagicMock()
        mock_res.registers = [100] * 50
        mock_res.bits = [True] * 50
        mock_res.isError.return_value = False
        return mock_res

    mock_client.read_holding_registers.side_effect = mock_read
    mock_client.read_input_registers.side_effect = mock_read
    mock_client.read_discrete_inputs.side_effect = mock_read
    mock_client.read_coils.side_effect = mock_read
    mock_client.write_register = AsyncMock()
    mock_client.write_registers = AsyncMock()

    # Still need to mock DNS because conftest doesn't do it
    with patch(
        "homeassistant.components.qube_heatpump.client.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.10", 502))],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Check that an entity was created and has a state.
    states = hass.states.async_all()
    assert len(states) > 0, "No entities were created"

    # Verify at least one specific sensor is available
    qube_entities = [s for s in states if s.entity_id.startswith("sensor.")]
    assert len(qube_entities) > 0

    # Check if the data is stored
    assert entry.runtime_data is not None
