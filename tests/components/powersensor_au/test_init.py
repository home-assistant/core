"""Tests for initial setup, migration, and teardown of the Powersensor component."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.powersensor_au import (
    _STARTUP_RESCAN_DELAYS,
    RESCAN_INTERVAL,
)
from homeassistant.components.powersensor_au.config_flow import PowersensorConfigFlow
from homeassistant.components.powersensor_au.const import DOMAIN, ROLE_SOLAR
from homeassistant.components.powersensor_au.models import PowersensorRuntimeData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MAC = "a4cf1218f158"


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test that the component loads without error."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


async def test_setup_unload_entry(
    hass: HomeAssistant,
    def_config_entry,
) -> None:
    """Test that setup populates runtime_data and unload cleans it up."""
    def_config_entry.add_to_hass(hass)
    mock_devices = def_config_entry.runtime_data.devices

    with patch(
        "homeassistant.components.powersensor_au.PowersensorDevices",
        return_value=mock_devices,
    ):
        assert await hass.config_entries.async_setup(def_config_entry.entry_id)
        await hass.async_block_till_done()
        assert hasattr(def_config_entry, "runtime_data")
        assert isinstance(def_config_entry.runtime_data, PowersensorRuntimeData)

        assert await hass.config_entries.async_unload(def_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_devices.stop.assert_called_once()


async def test_unload_skips_teardown_when_platform_unload_fails(
    hass: HomeAssistant,
    def_config_entry,
) -> None:
    """Test that dispatcher.disconnect() and devices.stop() are NOT called when async_unload_platforms returns False."""
    def_config_entry.add_to_hass(hass)
    mock_devices = def_config_entry.runtime_data.devices

    with patch(
        "homeassistant.components.powersensor_au.PowersensorDevices",
        return_value=mock_devices,
    ):
        assert await hass.config_entries.async_setup(def_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_devices.stop.reset_mock()

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        result = await hass.config_entries.async_unload(def_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    mock_devices.stop.assert_not_called()


async def test_setup_devices_start_failure_raises_config_entry_not_ready(
    hass: HomeAssistant,
    def_config_entry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a RuntimeError from devices.start() raises ConfigEntryNotReady."""
    def_config_entry.add_to_hass(hass)

    err_msg = "Forced start failure"
    stop_called = []

    mock_devices = MagicMock()
    mock_devices.start = AsyncMock(side_effect=RuntimeError(err_msg))
    mock_devices.stop = AsyncMock(side_effect=lambda: stop_called.append(True))

    with patch(
        "homeassistant.components.powersensor_au.PowersensorDevices",
        return_value=mock_devices,
    ):
        await hass.config_entries.async_setup(def_config_entry.entry_id)
        await hass.async_block_till_done()

    assert def_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert stop_called, (
        "devices.stop() must be called to clean up after a failed start()"
    )


async def test_migrate_entry(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test config-entry migration from v1 to the current version, reject new and accept current."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"0123456789ab": {}},
        entry_id="test_migrate",
        version=1,
        minor_version=1,
    )
    old_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.powersensor_au.PowersensorDevices",
    ) as mock_devices_cls:
        mock_devices_cls.return_value.start = AsyncMock(return_value=0)
        mock_devices_cls.return_value.stop = AsyncMock()
        mock_devices_cls.return_value.subscribe = MagicMock()
        mock_devices_cls.return_value.rescan = AsyncMock()
        await hass.config_entries.async_setup(old_entry.entry_id)
        await hass.async_block_till_done()

    assert old_entry.version == PowersensorConfigFlow.VERSION
    assert old_entry.minor_version == 2
    assert "roles" in old_entry.data

    too_new_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"0123456789ab": {}},
        entry_id="test_migrate_too_new",
        version=PowersensorConfigFlow.VERSION + 1,
        minor_version=1,
    )
    too_new_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(too_new_entry.entry_id)
    await hass.async_block_till_done()
    assert too_new_entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_setup_registers_rescan_callbacks(
    hass: HomeAssistant,
    def_config_entry,
) -> None:
    """Test that the correct number of startup rescans and one periodic interval are registered."""
    def_config_entry.add_to_hass(hass)

    call_later_calls = []
    track_interval_calls = []

    mock_devices = def_config_entry.runtime_data.devices

    def _fake_call_later(hass: HomeAssistant | None, delay, job):
        call_later_calls.append(delay)
        return lambda: None

    def _fake_track_interval(hass: HomeAssistant | None, cb, interval):
        track_interval_calls.append(interval)
        return lambda: None

    with (
        patch(
            "homeassistant.components.powersensor_au.PowersensorDevices",
            return_value=mock_devices,
        ),
        patch(
            "homeassistant.components.powersensor_au.async_call_later",
            side_effect=_fake_call_later,
        ),
        patch(
            "homeassistant.components.powersensor_au.async_track_time_interval",
            side_effect=_fake_track_interval,
        ),
    ):
        assert await hass.config_entries.async_setup(def_config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(call_later_calls) == len(_STARTUP_RESCAN_DELAYS)
    assert sorted(call_later_calls) == sorted(_STARTUP_RESCAN_DELAYS)
    assert len(track_interval_calls) == 1


def test_rescan_interval_is_five_minutes() -> None:
    """RESCAN_INTERVAL must be exactly 5 minutes."""
    assert timedelta(minutes=5) == RESCAN_INTERVAL


def test_startup_rescan_delays_are_graduated() -> None:
    """_STARTUP_RESCAN_DELAYS must be a non-empty strictly increasing sequence."""
    delays = _STARTUP_RESCAN_DELAYS
    assert len(delays) > 0
    assert delays[0] <= 15, "First rescan should fire within 15 seconds of startup"
    assert list(delays) == sorted(delays), "Delays must be in ascending order"


async def test_setup_constructs_vhh_with_solar_when_solar_role_persisted(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that VirtualHousehold is constructed with with_solar=True when a solar role is present."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"roles": {"aabbccddeeff": ROLE_SOLAR}},
        entry_id="test_solar",
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    constructed_with_solar = []

    class CapturingVHH:
        def __init__(self, with_solar: bool) -> None:
            constructed_with_solar.append(with_solar)
            self._with_solar = with_solar

        async def process_average_power_event(self, msg):
            pass

        async def process_summation_event(self, msg):
            pass

        def subscribe(self, *a):
            pass

        def unsubscribe(self, *a):
            pass

    mock_devices = MagicMock()
    mock_devices.start = AsyncMock(return_value=0)
    mock_devices.stop = AsyncMock()
    mock_devices.subscribe = MagicMock()
    mock_devices.rescan = AsyncMock()

    with (
        patch("homeassistant.components.powersensor_au.VirtualHousehold", CapturingVHH),
        patch(
            "homeassistant.components.powersensor_au.PowersensorDevices",
            return_value=mock_devices,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert constructed_with_solar == [True], (
        "VirtualHousehold must be constructed with with_solar=True when a solar "
        "role is present in entry.data"
    )


async def test_setup_raises_config_entry_not_ready_on_unexpected_setup_error(
    hass: HomeAssistant,
    def_config_entry,
) -> None:
    """Test that ValueError during VHH construction results in SETUP_RETRY state."""
    def_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.powersensor_au.VirtualHousehold",
        side_effect=ValueError("bad config"),
    ):
        await hass.config_entries.async_setup(def_config_entry.entry_id)
        await hass.async_block_till_done()

    assert def_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_rescan_fires_devices_rescan(
    hass: HomeAssistant,
    def_config_entry,
) -> None:
    """Test that the periodic _rescan callback calls devices.rescan()."""
    def_config_entry.add_to_hass(hass)
    mock_devices = def_config_entry.runtime_data.devices

    captured_rescan_cb = []

    def capture_interval(hass_arg, cb, interval):
        captured_rescan_cb.append(cb)
        return lambda: None

    with (
        patch(
            "homeassistant.components.powersensor_au.PowersensorDevices",
            return_value=mock_devices,
        ),
        patch(
            "homeassistant.components.powersensor_au.async_track_time_interval",
            side_effect=capture_interval,
        ),
    ):
        assert await hass.config_entries.async_setup(def_config_entry.entry_id)
        await hass.async_block_till_done()

    assert captured_rescan_cb, "async_track_time_interval was never called"
    await captured_rescan_cb[0](None)

    mock_devices.rescan.assert_awaited_once()


async def test_hass_started_event_triggers_rescan(
    hass: HomeAssistant,
    def_config_entry,
) -> None:
    """Test that EVENT_HOMEASSISTANT_STARTED triggers a rescan."""
    def_config_entry.add_to_hass(hass)
    mock_devices = def_config_entry.runtime_data.devices

    with patch(
        "homeassistant.components.powersensor_au.PowersensorDevices",
        return_value=mock_devices,
    ):
        assert await hass.config_entries.async_setup(def_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_devices.rescan.reset_mock()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    mock_devices.rescan.assert_awaited_once()
