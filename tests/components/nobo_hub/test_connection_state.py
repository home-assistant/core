"""Tests for Nobø Ecohub connection-state handling."""

import logging
from unittest.mock import MagicMock

import pytest

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant

from . import fire_hub_connection

from tests.common import MockConfigEntry

GLOBAL_ENTITY = "select.my_eco_hub_global_override"


@pytest.fixture
def platforms(request: pytest.FixtureRequest) -> list[Platform]:
    """Default to select; override per-test via indirect parametrize."""
    return getattr(request, "param", [Platform.SELECT])


@pytest.mark.usefixtures("init_integration")
async def test_entity_available_when_hub_connected(hass: HomeAssistant) -> None:
    """Entities are available when the hub reports connected."""
    state = hass.states.get(GLOBAL_ENTITY)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize("hub_connected", [False])
@pytest.mark.usefixtures("init_integration")
async def test_entity_unavailable_when_hub_disconnected_at_setup(
    hass: HomeAssistant,
) -> None:
    """Entities seed _attr_available from hub.connected at creation."""
    assert hass.states.get(GLOBAL_ENTITY).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_entity_unavailable_on_disconnect_and_recovers(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """Entities become unavailable on disconnect and recover on reconnect."""
    assert hass.states.get(GLOBAL_ENTITY).state != STATE_UNAVAILABLE

    await fire_hub_connection(hass, mock_nobo_hub, False)
    assert hass.states.get(GLOBAL_ENTITY).state == STATE_UNAVAILABLE

    await fire_hub_connection(hass, mock_nobo_hub, True)
    assert hass.states.get(GLOBAL_ENTITY).state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_log_on_disconnect_and_reconnect(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Disconnects log a warning; reconnects log info."""
    with caplog.at_level(logging.INFO, logger="homeassistant.components.nobo_hub"):
        caplog.clear()
        await fire_hub_connection(hass, mock_nobo_hub, False)
        assert any(
            record.levelno == logging.INFO
            and "Lost connection to Nobø Ecohub" in record.message
            for record in caplog.records
        )

        caplog.clear()
        await fire_hub_connection(hass, mock_nobo_hub, True)
        assert any(
            record.levelno == logging.INFO
            and "Reconnected to Nobø Ecohub" in record.message
            for record in caplog.records
        )


@pytest.mark.usefixtures("init_integration")
async def test_connection_callbacks_deregistered_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nobo_hub: MagicMock,
) -> None:
    """Every registered connection callback is deregistered on entry unload."""
    registered = mock_nobo_hub.register_connection_callback.call_count
    assert registered > 0

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_nobo_hub.deregister_connection_callback.call_count == registered


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE]], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_zone_removed_during_disconnect_stays_unavailable_on_reconnect(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """A zone removed via the Nobø app while disconnected stays unavailable on reconnect.

    The connection callback fires before the data callback (pynobo Option C).
    Without the `available` property's existence check, the connection callback's
    `_attr_available = True` would briefly flip the entity to available before the
    data callback's _read_state could re-mark it unavailable.
    """
    entity = "climate.living_room"
    assert hass.states.get(entity).state != STATE_UNAVAILABLE

    await fire_hub_connection(hass, mock_nobo_hub, False)
    assert hass.states.get(entity).state == STATE_UNAVAILABLE

    # Simulate the zone being removed via the Nobø app while disconnected:
    # by the time the hub reconnects and _get_initial_data runs, hub.zones
    # no longer contains the zone.
    mock_nobo_hub.zones = {}

    await fire_hub_connection(hass, mock_nobo_hub, True)
    assert hass.states.get(entity).state == STATE_UNAVAILABLE
