"""Tests for the Duosida EV Charger integration setup."""

from datetime import timedelta
import logging
from unittest.mock import MagicMock

from duosida_ev import (
    ChargerInfo,
    ChargerStatus,
    DuosidaConnectionError,
    DuosidaTimeoutError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.duosida_ev.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import push_update, setup_integration
from .conftest import CHARGER_INFO, DEVICE_ID, charger_status

POWER_ENTITY_ID = "sensor.duosida_ev_charger_power"
OTHER_CHARGER = ChargerInfo(device_id="0300000000000000001")


async def _fire_watchdog(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the refresh run, as it does when no push arrived for a while."""
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duosida_client: MagicMock,
) -> None:
    """Test the session opens on setup and closes on unload."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_duosida_client.connect.assert_awaited_once()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_duosida_client.disconnect.assert_awaited()
    mock_duosida_client.add_listener.return_value.assert_called()


@pytest.mark.parametrize(
    ("method", "side_effect"),
    [
        pytest.param("connect", DuosidaConnectionError, id="cannot_connect"),
        pytest.param("connect", DuosidaTimeoutError, id="no_identity"),
        pytest.param("connect", [OTHER_CHARGER], id="unexpected_device"),
        pytest.param("get_status", DuosidaTimeoutError, id="no_status"),
    ],
)
async def test_setup_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duosida_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
    method: str,
    side_effect: type[Exception] | list[ChargerInfo],
) -> None:
    """Test a failed setup closes the session and retries a minute later."""
    getattr(mock_duosida_client, method).side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_duosida_client.disconnect.assert_awaited()
    # The charger refuses fast reconnects.
    assert "Retrying in 60 seconds" in caplog.text
    # Config entry setup logs the retries; nothing else may log an error.
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]


async def test_setup_connection_lost(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duosida_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a session that drops during setup only logs the setup retry."""

    async def get_status(timeout: float) -> ChargerStatus:
        mock_duosida_client.connected = False
        push_update(mock_duosida_client)
        raise DuosidaConnectionError

    mock_duosida_client.get_status.side_effect = get_status

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]


async def test_session_closed_on_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duosida_client: MagicMock,
) -> None:
    """Test the session is closed cleanly when Home Assistant stops."""
    await setup_integration(hass, mock_config_entry)
    mock_duosida_client.disconnect.assert_not_awaited()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_duosida_client.disconnect.assert_awaited_once()


@pytest.mark.usefixtures("mock_duosida_client")
async def test_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry comes from the charger's identity."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_ID), mock_config_entry.entry_id
    )
    assert device == snapshot


async def test_push_updates_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duosida_client: MagicMock,
) -> None:
    """Test a status pushed by the charger updates the entities."""
    await setup_integration(hass, mock_config_entry)

    mock_duosida_client.status = charger_status(power=1234.5)
    push_update(mock_duosida_client)

    assert hass.states.get(POWER_ENTITY_ID).state == "1234.5"


async def test_reconnect_after_connection_lost(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duosida_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a dropped session is unavailable until the watchdog reconnects it."""
    await setup_integration(hass, mock_config_entry)

    mock_duosida_client.connected = False
    mock_duosida_client.connect.side_effect = DuosidaConnectionError
    push_update(mock_duosida_client)

    assert hass.states.get(POWER_ENTITY_ID).state == STATE_UNAVAILABLE

    # The charger refuses the first reconnects.
    await _fire_watchdog(hass, freezer)
    await _fire_watchdog(hass, freezer)

    assert hass.states.get(POWER_ENTITY_ID).state == STATE_UNAVAILABLE
    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert "The connection to the charger was lost" in errors[0].getMessage()

    async def connect() -> ChargerInfo:
        mock_duosida_client.connected = True
        return CHARGER_INFO

    async def get_status(timeout: float) -> ChargerStatus:
        # The push that answers the refresh reaches the listener first.
        mock_duosida_client.status = charger_status(power=99.0)
        push_update(mock_duosida_client)
        return mock_duosida_client.status

    mock_duosida_client.connect.side_effect = connect
    mock_duosida_client.get_status.side_effect = get_status
    await _fire_watchdog(hass, freezer)

    assert hass.states.get(POWER_ENTITY_ID).state == "99.0"
    assert "Fetching duosida_ev data recovered" in caplog.text


@pytest.mark.parametrize(
    ("side_effect", "message", "disconnects"),
    [
        # Heartbeats can hold a session open after the status pushes stop.
        pytest.param(
            DuosidaTimeoutError,
            "The charger did not send its status",
            1,
            id="silent_session_closed",
        ),
        pytest.param(
            DuosidaConnectionError,
            "The connection to the charger was lost",
            0,
            id="connection_error",
        ),
    ],
)
async def test_refresh_without_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duosida_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    side_effect: type[Exception],
    message: str,
    disconnects: int,
) -> None:
    """Test the entities go unavailable when the watchdog gets no status."""
    await setup_integration(hass, mock_config_entry)
    mock_duosida_client.get_status.side_effect = side_effect

    await _fire_watchdog(hass, freezer)

    assert hass.states.get(POWER_ENTITY_ID).state == STATE_UNAVAILABLE
    assert message in caplog.text
    assert mock_duosida_client.disconnect.await_count == disconnects
