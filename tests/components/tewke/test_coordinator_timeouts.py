"""Test Tewke coordinator timeouts."""

import asyncio
import logging
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.tewke.coordinator import TewkeCoordinator, UpdateFailed
from homeassistant.components.tewke.data import TewkeData
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_tap")


async def test_coordinator_reset_and_cancel_timeout(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test reset and cancel timeout logic."""
    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
        observe_active=False,
    )

    coordinator = TewkeCoordinator(
        hass, logging.getLogger(__name__), "Tewke Tap", mock_config_entry
    )

    with patch(
        "homeassistant.components.tewke.coordinator.async_call_later",
        side_effect=lambda *args: MagicMock(),
    ) as mock_call_later:
        coordinator.reset_observation_timeout()
        assert mock_call_later.call_count == 1
        assert coordinator._observation_timeout_unsub is not None

        # Call it again to trigger the cancel of existing
        mock_unsub = coordinator._observation_timeout_unsub
        coordinator.reset_observation_timeout()
        assert mock_call_later.call_count == 2
        assert mock_unsub is not None
        cast(MagicMock, mock_unsub).assert_called_once()

        # Now cancel
        mock_unsub2 = coordinator._observation_timeout_unsub
        coordinator.cancel_observation_timeout()
        assert mock_unsub2 is not None
        cast(MagicMock, mock_unsub2).assert_called_once()
        assert coordinator._observation_timeout_unsub is None


async def test_coordinator_handle_timeout_retry_success_first_try(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test when the first retry attempt (retry_observes) succeeds."""
    mock_tap.retry_observes = AsyncMock(return_value=True)

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
        observe_active=False,
    )

    coordinator = TewkeCoordinator(
        hass, logging.getLogger(__name__), "Tewke Tap", mock_config_entry
    )

    # We call handle_observation_timeout
    with patch.object(coordinator, "reset_observation_timeout") as mock_reset:
        coordinator._handle_observation_timeout(utcnow())
        if coordinator._observe_retry_task is not None:
            await coordinator._observe_retry_task

        mock_tap.retry_observes.assert_called_once()
        mock_reset.assert_called_once()
        assert mock_config_entry.runtime_data.observe_active is True
        assert coordinator._observe_retry_task is None


async def test_coordinator_handle_timeout_retry_success_second_try(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test when retry_observes fails but _setup_observe succeeds."""
    mock_tap.retry_observes = AsyncMock(return_value=False)

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
        observe_active=False,
    )

    coordinator = TewkeCoordinator(
        hass, logging.getLogger(__name__), "Tewke Tap", mock_config_entry
    )

    with (
        patch.object(
            coordinator, "_setup_observe", return_value=True
        ) as mock_setup_observe,
        patch(
            "homeassistant.components.tewke.coordinator.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
    ):
        coordinator._handle_observation_timeout(utcnow())
        if coordinator._observe_retry_task is not None:
            await coordinator._observe_retry_task

        mock_tap.retry_observes.assert_called_once()
        mock_sleep.assert_called_once()  # Slept once before second try
        mock_setup_observe.assert_called_once()


async def test_coordinator_handle_timeout_retry_fail_all(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test when all retry attempts fail."""
    mock_tap.retry_observes = AsyncMock(return_value=False)

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
        observe_active=False,
    )

    coordinator = TewkeCoordinator(
        hass, logging.getLogger(__name__), "Tewke Tap", mock_config_entry
    )

    with (
        patch.object(
            coordinator, "_setup_observe", return_value=False
        ) as mock_setup_observe,
        patch(
            "homeassistant.components.tewke.coordinator.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        patch.object(coordinator, "async_set_update_error") as mock_set_error,
    ):
        coordinator._handle_observation_timeout(utcnow())
        if coordinator._observe_retry_task is not None:
            await coordinator._observe_retry_task

        assert (
            mock_setup_observe.call_count == 2
        )  # len(_observe_delays) is 3, first is retry_observes, then 2 calls to setup_observe
        assert mock_sleep.call_count == 2
        mock_set_error.assert_called_once()

        # Ensure that it correctly passed the error
        err = mock_set_error.call_args[0][0]
        assert isinstance(err, UpdateFailed)


async def test_coordinator_handle_timeout_already_running(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test when _handle_observation_timeout is called while a retry is already running."""
    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
        observe_active=False,
    )

    coordinator = TewkeCoordinator(
        hass, logging.getLogger(__name__), "Tewke Tap", mock_config_entry
    )

    dummy_task = MagicMock()
    dummy_task.done.return_value = False
    coordinator._observe_retry_task = dummy_task

    # This should return early and not spawn a new task
    coordinator._handle_observation_timeout(utcnow())
    assert coordinator._observe_retry_task is dummy_task


async def test_coordinator_cancel_timeout_with_task(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test cancel_observation_timeout when a task is running."""
    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
        observe_active=False,
    )

    coordinator = TewkeCoordinator(
        hass, logging.getLogger(__name__), "Tewke Tap", mock_config_entry
    )

    dummy_task = MagicMock()
    dummy_task.done.return_value = False
    coordinator._observe_retry_task = dummy_task

    coordinator.cancel_observation_timeout()

    dummy_task.cancel.assert_called_once()
    assert coordinator._observe_retry_task is None


async def test_coordinator_retry_task_yields(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test that retry correctly clears the task reference when yielding."""

    # We want retry_observes to yield, so we use a real async function for side_effect
    async def mock_retry_observes():

        await asyncio.sleep(0)
        return True

    mock_tap.retry_observes.side_effect = mock_retry_observes

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
        observe_active=False,
    )

    coordinator = TewkeCoordinator(
        hass, logging.getLogger(__name__), "Tewke Tap", mock_config_entry
    )

    with patch.object(coordinator, "reset_observation_timeout"):
        coordinator._handle_observation_timeout(utcnow())
        assert coordinator._observe_retry_task is not None
        await coordinator._observe_retry_task
        assert coordinator._observe_retry_task is None
