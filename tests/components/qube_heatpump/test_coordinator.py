"""Tests for the Qube Heat Pump coordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from python_qube_heatpump.models import QubeState

from homeassistant.components.qube_heatpump.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed


def get_entity_id_by_unique_id_suffix(
    hass: HomeAssistant, entry_unique_id: str, key: str
) -> str | None:
    """Get entity_id from entity registry by unique_id suffix."""
    entity_registry = er.async_get(hass)
    unique_id = f"{entry_unique_id}-{key}"
    return entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)


async def test_coordinator_fetches_data(
    hass: HomeAssistant, mock_qube_client: MagicMock
) -> None:
    """Test coordinator fetches data from hub."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        title="Qube Heat Pump",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Assert config entry state
    assert entry.state is ConfigEntryState.LOADED

    # Assert entity state via core state machine - data was fetched
    states = hass.states.async_all()
    sensor_states = [s for s in states if s.entity_id.startswith("sensor.")]
    assert len(sensor_states) > 0
    # At least one sensor should have a valid (non-unavailable) state
    valid_states = [s for s in sensor_states if s.state != STATE_UNAVAILABLE]
    assert len(valid_states) > 0


async def test_coordinator_reconnects_when_disconnected(
    hass: HomeAssistant,
) -> None:
    """Test coordinator reconnects when client is disconnected."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1
        client.is_connected = False  # Start disconnected

        async def _connect() -> bool:
            client.is_connected = True
            return True

        client.connect = AsyncMock(side_effect=_connect)
        client.close = AsyncMock(return_value=None)

        state = QubeState()
        state.temp_supply = 45.0
        state.status_code = 1
        client.get_all_data = AsyncMock(return_value=state)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert config entry state
        assert entry.state is ConfigEntryState.LOADED

        # Connection should have been attempted since is_connected was False
        client.connect.assert_called()


async def test_coordinator_handles_fetch_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles fetch errors gracefully."""
    state = QubeState()
    state.temp_supply = 45.0
    state.status_code = 1

    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1
        client.is_connected = True
        client.connect = AsyncMock(return_value=True)
        client.close = AsyncMock(return_value=None)
        # First call succeeds for setup
        client.get_all_data = AsyncMock(return_value=state)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
            unique_id=f"{DOMAIN}-1.2.3.4-502",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert initial state is loaded
        assert entry.state is ConfigEntryState.LOADED

        # Look up entity by unique_id via entity registry
        entity_id = get_entity_id_by_unique_id_suffix(
            hass, entry.unique_id, "temp_supply"
        )
        assert entity_id is not None
        sensor_state = hass.states.get(entity_id)
        assert sensor_state is not None
        assert float(sensor_state.state) == 45.0

        # Make next fetch fail
        client.get_all_data.side_effect = Exception("Communication error")

        # Trigger coordinator refresh via time advancement
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # Entry should still be loaded (coordinator handles errors gracefully)
        assert entry.state is ConfigEntryState.LOADED


async def test_coordinator_handles_no_data(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles no data response gracefully."""
    state = QubeState()
    state.temp_supply = 45.0
    state.status_code = 1

    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1
        client.is_connected = True
        client.connect = AsyncMock(return_value=True)
        client.close = AsyncMock(return_value=None)
        # First call succeeds for setup
        client.get_all_data = AsyncMock(return_value=state)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            title="Qube Heat Pump",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert initial state is loaded
        assert entry.state is ConfigEntryState.LOADED

        # Make next fetch return None
        client.get_all_data.return_value = None

        # Trigger coordinator refresh via time advancement
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # Entry should still be loaded
        assert entry.state is ConfigEntryState.LOADED
