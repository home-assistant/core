"""Tests for the Qube Heat Pump integration setup and unloading."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from python_qube_heatpump.models import QubeState

from homeassistant.components.qube_heatpump.const import CONF_HOST, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry_registers_integration(
    hass: HomeAssistant,
) -> None:
    """Test setup entry registers the integration and creates entities."""
    state = QubeState()
    state.temp_supply = 45.0
    state.status_code = 1

    client = MagicMock()
    client.host = "1.2.3.4"
    client.port = 502
    client.unit = 1
    client.connect = AsyncMock(return_value=True)
    client.is_connected = True
    client.close = AsyncMock(return_value=None)
    client.get_all_data = AsyncMock(return_value=state)

    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient",
        return_value=client,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert config entry state via ConfigEntry.state attribute
        assert entry.state is ConfigEntryState.LOADED

        # Assert entity state via core state machine
        states = hass.states.async_all()
        sensor_states = [s for s in states if s.entity_id.startswith("sensor.")]
        assert len(sensor_states) > 0


async def test_async_unload_entry_cleans_up(
    hass: HomeAssistant,
) -> None:
    """Ensure unload removes stored data and closes the hub."""
    state = QubeState()
    state.temp_supply = 45.0
    state.status_code = 1

    client = MagicMock()
    client.host = "1.2.3.4"
    client.port = 502
    client.unit = 1
    client.connect = AsyncMock(return_value=True)
    client.is_connected = True
    client.close = AsyncMock(return_value=None)
    client.get_all_data = AsyncMock(return_value=state)

    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient",
        return_value=client,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        # Unload via config entries interface
        result = await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert result is True
        # Assert config entry state after unload
        assert entry.state is ConfigEntryState.NOT_LOADED
        # Verify close was called
        client.close.assert_called()
