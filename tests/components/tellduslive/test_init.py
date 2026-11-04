"""Tests for the TelldusLive integration setup."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.tellduslive.api import (
    TelldusLiveError,
    TelldusLiveRateLimitError,
)
from homeassistant.components.tellduslive.const import (
    DOMAIN,
    KEY_RETRY_INITIAL_DELAY,
    KEY_RETRY_MAX_DELAY,
)
from homeassistant.config_entries import ConfigEntryState
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

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == "Authentication with Telldus Live failed"


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
    client._failures = failures

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
    client._failures = 3

    assert client._retry_delay(TelldusLiveError("x")) == 8


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
