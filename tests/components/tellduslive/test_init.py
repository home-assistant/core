"""Tests for the TelldusLive integration setup."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.tellduslive import async_remove_config_entry_device
from homeassistant.components.tellduslive.api import (
    TelldusLiveError,
    TelldusLiveRateLimitError,
)
from homeassistant.components.tellduslive.const import (
    DOMAIN,
    KEY_RETRY_INITIAL_DELAY,
    KEY_RETRY_MAX_DELAY,
    KEY_SCAN_INTERVAL,
    RETRY_RESET_AFTER_OK,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .conftest import DEVICE_ID, HUB_ID


async def test_device_via_device_links(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test that a discovered device links to its hub via via_device_id."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    # Hubs and devices are registered from a background task spawned by setup.
    await mock_config_entry.runtime_data.setup_task
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    hub_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, HUB_ID), mock_config_entry.entry_id
    )
    assert hub_device is not None

    child_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_ID), mock_config_entry.entry_id
    )
    assert child_device is not None
    assert child_device.via_device_id == hub_device.id
    assert hass.states.async_all("switch")

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert all(
        state.state == STATE_UNAVAILABLE for state in hass.states.async_all("switch")
    )


async def test_device_added_without_hub(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test a device is still added, unlinked, when its hub is not registered."""
    # A failed clients/list request yields an empty hub list, so no hub is registered.
    mock_tellduslive.get_clients.return_value = []
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await mock_config_entry.runtime_data.setup_task
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, HUB_ID), mock_config_entry.entry_id
        )
        is None
    )

    child_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_ID), mock_config_entry.entry_id
    )
    assert child_device is not None
    assert child_device.via_device_id is None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_setup_not_authorized(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test setup fails when the session is not authorized."""
    mock_tellduslive.is_authorized = False
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.tellduslive.config_flow.Session"):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == "Authentication with Telldus Live failed"
    assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_no_polling_after_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test an update finishing after unload does not schedule another."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await mock_config_entry.runtime_data.setup_task
    await hass.async_block_till_done()
    client = mock_config_entry.runtime_data.client

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    # Simulate an update that was in flight while the entry unloaded.
    await client.update()
    mock_tellduslive.update.reset_mock()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    mock_tellduslive.update.assert_not_called()


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    if entry.entry_id not in {e.entry_id for e in hass.config_entries.async_entries()}:
        entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await entry.runtime_data.setup_task
    await hass.async_block_till_done()


async def test_rate_limited_setup_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a 429 does not fail setup, is logged and retried after Retry-After."""
    mock_tellduslive.update.side_effect = TelldusLiveRateLimitError("limited", 120)

    await _setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.states.async_all("switch")
    assert "retrying in 120" in caplog.text
    assert any(record.levelname == "WARNING" for record in caplog.records)
    assert mock_tellduslive.update.call_count == 1

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()
    assert mock_tellduslive.update.call_count == 1

    mock_tellduslive.update.side_effect = None
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=121))
    await hass.async_block_till_done()
    assert mock_tellduslive.update.call_count == 2
    assert hass.states.async_all("switch")


async def test_restore_from_snapshot(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test entities are created from the stored snapshot while the API is down."""
    state = {DEVICE_ID: {"id": "1", "name": "Kitchen"}}
    hass_storage[f"{DOMAIN}.{mock_config_entry.entry_id}"] = {
        "version": 1,
        "minor_version": 1,
        "key": f"{DOMAIN}.{mock_config_entry.entry_id}",
        "data": {
            "state": state,
            "device_infos": {DEVICE_ID: {"model": "x", "client": HUB_ID}},
        },
    }
    mock_tellduslive.get_clients.side_effect = TelldusLiveError("down")

    await _setup(hass, mock_config_entry)

    mock_tellduslive.load_state.assert_called_once_with(state)
    mock_tellduslive.info.assert_not_called()
    assert hass.states.async_all("switch")
    assert all(
        state.state != STATE_UNAVAILABLE for state in hass.states.async_all("switch")
    )


async def test_snapshot_saved_after_refresh(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test a successful refresh stores the snapshot."""
    await _setup(hass, mock_config_entry)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()

    assert hass_storage[f"{DOMAIN}.{mock_config_entry.entry_id}"]["data"] == {
        "state": {},
        "device_infos": {DEVICE_ID: mock_tellduslive.device().info()},
    }


async def test_remove_entry_deletes_snapshot_for_good(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test removing the entry within the save delay leaves no snapshot behind."""
    key = f"{DOMAIN}.{mock_config_entry.entry_id}"
    await _setup(hass, mock_config_entry)
    assert key not in hass_storage

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    assert key not in hass_storage

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    assert key not in hass_storage


async def test_unload_flushes_snapshot(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test unloading within the save delay still keeps the snapshot."""
    await _setup(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert f"{DOMAIN}.{mock_config_entry.entry_id}" in hass_storage


@pytest.mark.parametrize(
    ("failures", "retry_after", "expected"),
    [
        (1, None, 30),
        (2, None, 60),
        (3, None, 120),
        (10, None, 900),
        (1, 300, 300),
        (10, 300, 900),
    ],
)
async def test_retry_delay(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
    failures: int,
    retry_after: float | None,
    expected: float,
) -> None:
    """Test the exponential backoff, capped and honoring Retry-After."""
    await _setup(hass, mock_config_entry)
    client = mock_config_entry.runtime_data.client
    client._backoff = failures

    assert client._retry_delay(TelldusLiveRateLimitError("x", retry_after)) == expected


async def test_retry_options_used(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test retry delays come from the options."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            KEY_RETRY_INITIAL_DELAY: 5,
            KEY_RETRY_MAX_DELAY: 8,
        },
    )
    await _setup(hass, mock_config_entry)
    client = mock_config_entry.runtime_data.client
    client._backoff = 3

    assert client._retry_delay(TelldusLiveError("x")) == 8


@pytest.mark.parametrize(
    ("ok_refreshes", "expected_backoff"),
    [
        pytest.param(1, 3, id="one_ok_keeps_backoff"),
        pytest.param(RETRY_RESET_AFTER_OK - 1, 3, id="almost_enough_oks"),
        pytest.param(RETRY_RESET_AFTER_OK, 0, id="enough_oks_resets"),
    ],
)
async def test_backoff_resets_after_consecutive_oks(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
    ok_refreshes: int,
    expected_backoff: int,
) -> None:
    """Test the backoff only restarts after several OK refreshes in a row."""
    await _setup(hass, mock_config_entry)
    client = mock_config_entry.runtime_data.client
    client._backoff = 3
    client._failures = 3
    client._ok_streak = 0

    for _ in range(ok_refreshes):
        await client.update()

    assert client._backoff == expected_backoff
    assert client.status == "ok"


async def test_failure_breaks_ok_streak(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test a failure between OK refreshes restarts the OK count."""
    await _setup(hass, mock_config_entry)
    client = mock_config_entry.runtime_data.client
    client._backoff = 1
    client._failures = 1
    client._ok_streak = 0

    for _ in range(RETRY_RESET_AFTER_OK - 1):
        await client.update()
    mock_tellduslive.update.side_effect = TelldusLiveError("down")
    await client.update()
    mock_tellduslive.update.side_effect = None
    for _ in range(RETRY_RESET_AFTER_OK - 1):
        await client.update()

    assert client._backoff == 2


async def test_options_applied_without_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test changed options re-arm the timer and do not reload the entry."""
    await _setup(hass, mock_config_entry)
    mock_tellduslive.update.reset_mock()

    with patch.object(hass.config_entries, "async_reload") as mock_reload:
        hass.config_entries.async_update_entry(
            mock_config_entry,
            options={**mock_config_entry.options, KEY_SCAN_INTERVAL: 40},
        )
        await hass.async_block_till_done()

    mock_reload.assert_not_called()
    assert mock_config_entry.runtime_data.client._interval == 40

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=41))
    await hass.async_block_till_done()

    assert mock_tellduslive.update.call_count == 1


async def test_options_change_during_update_keeps_single_timer(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test an options change while refreshing does not add a second timer."""
    await _setup(hass, mock_config_entry)
    client = mock_config_entry.runtime_data.client
    mock_tellduslive.update.reset_mock()
    client._updating = True
    pending = client._cancel_update

    with patch(
        "homeassistant.components.tellduslive.async_call_later"
    ) as mock_call_later:
        client.async_options_updated()

    mock_call_later.assert_not_called()
    assert client._cancel_update is pending


async def test_command_rejected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test a command Telldus Live does not accept raises an error."""
    mock_tellduslive.device().turn_on.return_value = False
    await _setup(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError, match="did not accept the command"):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": "switch.kitchen"}, blocking=True
        )


async def test_status_lifecycle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test the status goes from starting to ok."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    client = mock_config_entry.runtime_data.client
    assert client.status == "starting"

    await mock_config_entry.runtime_data.setup_task
    await hass.async_block_till_done()

    assert client.status == "ok"


@pytest.mark.parametrize(
    ("failures", "expected"),
    [(1, "retrying"), (4, "retrying"), (5, "error"), (9, "error")],
)
async def test_status_after_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
    failures: int,
    expected: str,
) -> None:
    """Test retrying turns into error after repeated failures and recovers."""
    mock_tellduslive.update.side_effect = TelldusLiveError("down")
    await _setup(hass, mock_config_entry)
    client = mock_config_entry.runtime_data.client
    client._failures = failures - 1

    await client.update()

    assert client.status == expected

    mock_tellduslive.update.side_effect = None
    await client.update()

    assert client.status == "ok"


@pytest.mark.parametrize(
    ("identifier", "removable"),
    [
        pytest.param(DEVICE_ID, False, id="active_device"),
        pytest.param(HUB_ID, False, id="hub"),
        pytest.param("gone", True, id="stale_device"),
    ],
)
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
    device_registry: dr.DeviceRegistry,
    identifier: str,
    removable: bool,
) -> None:
    """Test only devices missing from the account can be removed."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await mock_config_entry.runtime_data.setup_task
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, identifier)},
    )

    assert (
        await async_remove_config_entry_device(hass, mock_config_entry, device)
        is removable
    )
