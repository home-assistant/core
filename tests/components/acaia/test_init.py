"""Test init of acaia integration."""

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from aioacaia.exceptions import AcaiaDeviceNotFound, AcaiaError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement_with_time_and_source,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.acaia.const import CONF_IDLE_TIMEOUT, DOMAIN
from homeassistant.components.bluetooth import MONOTONIC_TIME, SOURCE_LOCAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

pytestmark = pytest.mark.usefixtures("init_integration")

WEIGHT_ENTITY_ID = "sensor.kitchen_lunar_ddeeff_weight"

idle_timeout_5_minutes = pytest.mark.parametrize(
    "entry_options", [{CONF_IDLE_TIMEOUT: 5}]
)


@pytest.fixture(autouse=True)
def track_connection_state(mock_scale: MagicMock) -> None:
    """Make the mocked scale report its connection state like the real one."""

    async def _connect(**kwargs: Any) -> None:
        mock_scale.connected = True

    async def _disconnect() -> None:
        mock_scale.connected = False

    mock_scale.connect.side_effect = _connect
    mock_scale.disconnect.side_effect = _disconnect


def _advertise(hass: HomeAssistant, time: float) -> None:
    """Inject an advertisement from the scale, always with the same data."""
    inject_advertisement_with_time_and_source(
        hass,
        generate_ble_device("aa:bb:cc:dd:ee:ff", "LUNAR-DDEEFF"),
        generate_advertisement_data(local_name="LUNAR-DDEEFF"),
        time,
        SOURCE_LOCAL,
    )


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float
) -> None:
    """Advance time and let the integration poll."""
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _weight_state(hass: HomeAssistant) -> str:
    """Return the state of the weight entity."""
    state = hass.states.get(WEIGHT_ENTITY_ID)
    assert state
    return state.state


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_unload_disconnects_scale(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scale: MagicMock,
) -> None:
    """Test unloading the entry releases the connection."""
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_scale.disconnect.assert_called_once()


async def test_unload_cancels_pending_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unloading the entry does not wait for a slow connect from polling."""
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def _connect(**kwargs: Any) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    mock_scale.connected = False
    mock_scale.connect.side_effect = _connect

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await started.wait()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert cancelled.is_set()


async def test_no_reconnect_while_unloading(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test polling does not reconnect while unloading waits for the disconnect."""
    disconnecting = asyncio.Event()
    release = asyncio.Event()

    async def _disconnect() -> None:
        mock_scale.connected = False
        disconnecting.set()
        await release.wait()

    mock_scale.disconnect.side_effect = _disconnect

    unload = hass.async_create_task(
        hass.config_entries.async_unload(mock_config_entry.entry_id)
    )
    await disconnecting.wait()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await asyncio.sleep(0)
    mock_scale.connect.assert_not_called()

    release.set()
    await unload

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_scale.connected is False


async def test_scale_stays_connected_without_idle_timeout(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities stay available on an idle scale without an idle timeout."""
    await _tick(hass, freezer, 24 * 60)

    assert _weight_state(hass) != STATE_UNAVAILABLE


@idle_timeout_5_minutes
async def test_weight_change_resets_idle_timer(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_scale_class: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test only the time since the last weight change counts as idle."""
    notify = mock_scale_class.call_args.kwargs["notify_callback"]
    notify()

    await _tick(hass, freezer, 4)
    mock_scale.weight += 1
    notify()
    await _tick(hass, freezer, 4)
    assert _weight_state(hass) != STATE_UNAVAILABLE

    # An unchanged weight does not count as activity.
    notify()
    await _tick(hass, freezer, 1)
    assert _weight_state(hass) == STATE_UNAVAILABLE


@idle_timeout_5_minutes
@pytest.mark.parametrize(
    "polls_during_silence",
    [pytest.param(0, id="resumes_between_polls"), pytest.param(3, id="polled")],
)
async def test_reconnects_after_scale_turns_off_and_on(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
    polls_during_silence: int,
) -> None:
    """Test an idle disconnect holds until the scale has gone silent and returned."""
    await _tick(hass, freezer, 6)
    assert _weight_state(hass) == STATE_UNAVAILABLE
    disconnected_at = MONOTONIC_TIME()

    for _ in range(polls_during_silence):
        await _tick(hass, freezer, 1)
    assert _weight_state(hass) == STATE_UNAVAILABLE

    _advertise(hass, disconnected_at + 40)
    await _tick(hass, freezer, 1)
    assert _weight_state(hass) != STATE_UNAVAILABLE


@idle_timeout_5_minutes
async def test_no_reconnect_while_scale_advertises_after_idle_disconnect(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the scale is left alone while it keeps advertising unchanged data."""
    await _tick(hass, freezer, 6)
    disconnected_at = MONOTONIC_TIME()

    for advertisement in range(1, 6):
        _advertise(hass, disconnected_at + advertisement * 20)
        await _tick(hass, freezer, 1)
        assert _weight_state(hass) == STATE_UNAVAILABLE


@idle_timeout_5_minutes
async def test_no_advertising_while_connected_does_not_count_as_turned_off(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test silence from before the disconnect is ignored."""
    _advertise(hass, MONOTONIC_TIME() - 300)
    await _tick(hass, freezer, 6)
    assert _weight_state(hass) == STATE_UNAVAILABLE

    _advertise(hass, MONOTONIC_TIME() + 1)
    await _tick(hass, freezer, 1)
    assert _weight_state(hass) == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "exception", [AcaiaError, AcaiaDeviceNotFound("Boom"), TimeoutError]
)
async def test_update_exception_leads_to_active_disconnect(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test scale gets disconnected on exception."""

    mock_scale.connect.side_effect = exception
    mock_scale.connected = False

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_scale.device_disconnected_handler.assert_called_once()


async def test_device(
    mock_scale: MagicMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot the device from registry."""

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_scale.mac), mock_config_entry.entry_id
    )
    assert device
    assert device == snapshot
