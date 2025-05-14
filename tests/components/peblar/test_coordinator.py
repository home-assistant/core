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

pytestmark = [
    pytest.mark.parametrize("init_integration", [Platform.SENSOR], indirect=True),
    pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration"),
]


@pytest.mark.parametrize(
    ("error", "log_message"),
    [
        (
            PeblarConnectionError("Could not connect"),
            (
                "An error occurred while communicating with the Peblar EV charger: "
                "Could not connect"
            ),
        ),
        (
            PeblarError("Unknown error"),
            (
                "An unknown error occurred while communicating "
                "with the Peblar EV charger: Unknown error"
            ),
        ),
    ],
)
async def test_coordinator_error_handler(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    log_message: str,
) -> None:
    """Test the coordinators."""
    entity_id = "sensor.peblar_ev_charger_power"

    # Ensure we are set up and the coordinator is working.
    # Confirming this through a sensor entity, that is available.
    assert (state := hass.states.get(entity_id))
    assert state.state != STATE_UNAVAILABLE

    # Mock an error in the coordinator.
    mock_peblar.rest_api.return_value.meter.side_effect = error
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Ensure the sensor entity is now unavailable.
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE

    # Ensure the error is logged
    assert log_message in caplog.text

    # Recover
    mock_peblar.rest_api.return_value.meter.side_effect = None
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Ensure the sensor entity is now available.
    assert (state := hass.states.get("sensor.peblar_ev_charger_power"))
    assert state.state != STATE_UNAVAILABLE


async def test_coordinator_error_handler_authentication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator error handler with an authentication error."""

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
