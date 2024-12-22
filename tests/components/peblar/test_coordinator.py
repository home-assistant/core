"""Tests for the Peblar coordinators."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from peblar import PeblarAuthenticationError, PeblarConnectionError, PeblarError
import pytest

from homeassistant.components.peblar.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize("init_integration", [Platform.SENSOR], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_coordinator_error_handler(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the coordinators."""

    # Ensure we are set up and the coordinator is working.
    # Confirming this through a sensor entity, that is available.
    assert (state := hass.states.get("sensor.peblar_ev_charger_power"))
    assert state.state != STATE_UNAVAILABLE

    # Mock an error in the coordinator.
    mock_peblar.rest_api.return_value.meter.side_effect = PeblarConnectionError(
        "Could not connect"
    )
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Ensure the sensor entity is now unavailable.
    assert (state := hass.states.get("sensor.peblar_ev_charger_power"))
    assert state.state == STATE_UNAVAILABLE

    # Ensure the error is logged
    assert (
        "An error occurred while communicating with the Peblar device: "
        "Could not connect"
    ) in caplog.text

    # Recover
    mock_peblar.rest_api.return_value.meter.side_effect = None
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Ensure the sensor entity is now available.
    assert (state := hass.states.get("sensor.peblar_ev_charger_power"))
    assert state.state != STATE_UNAVAILABLE

    # Mock an error in the coordinator.
    mock_peblar.rest_api.return_value.meter.side_effect = PeblarError("Unknown error")
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Ensure the sensor entity is now unavailable.
    assert (state := hass.states.get("sensor.peblar_ev_charger_power"))
    assert state.state == STATE_UNAVAILABLE

    # Ensure the error is logged
    assert (
        "An unknown error occurred while communicating "
        "with the Peblar device: Unknown error"
    ) in caplog.text

    # Recover
    mock_peblar.rest_api.return_value.meter.side_effect = None
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Ensure the sensor entity is now available.
    assert (state := hass.states.get("sensor.peblar_ev_charger_power"))
    assert state.state != STATE_UNAVAILABLE

    # Mock an authentication in the coordinator
    mock_peblar.rest_api.return_value.meter.side_effect = PeblarAuthenticationError(
        "Authentication error"
    )
    mock_peblar.login.side_effect = PeblarAuthenticationError("Authentication error")
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Ensure the sensor entity is now unavailable.
    assert (state := hass.states.get("sensor.peblar_ev_charger_power"))
    assert state.state == STATE_UNAVAILABLE

    # Ensure we have triggered a reauthentication flow
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id
