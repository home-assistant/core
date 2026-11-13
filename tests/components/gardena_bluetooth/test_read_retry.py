"""Tests for bounded characteristic reads."""

import asyncio
import logging
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
from gardena_bluetooth.parse import Characteristic, CharacteristicSegmented
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.gardena_bluetooth.coordinator import (
    GardenaBluetoothCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.fixture
def coordinator(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: Mock
) -> GardenaBluetoothCoordinator:
    """Create a coordinator without starting polling."""
    return GardenaBluetoothCoordinator(
        hass, mock_entry, logging.getLogger(__name__), mock_client, "AA:BB:CC:DD:EE:FF"
    )


@pytest.mark.parametrize("failures", [0, 1])
async def test_read_recovery(
    coordinator: GardenaBluetoothCoordinator, failures: int
) -> None:
    """Successful reads and transient timeouts return data."""
    coordinator.client.read_char.side_effect = [TimeoutError()] * failures + [42]
    assert await coordinator._read_characteristic(Characteristic("test")) == 42
    assert coordinator.client.read_char.await_count == failures + 1


async def test_exhausted_retries(coordinator: GardenaBluetoothCoordinator) -> None:
    """Repeated timeouts fail the update with the characteristic ID."""
    coordinator.client.read_char.side_effect = TimeoutError
    with pytest.raises(UpdateFailed, match="Timeout reading test after 2 attempts"):
        await coordinator._read_characteristic(Characteristic("test"))
    assert coordinator.client.read_char.await_count == 2


async def test_read_cancellation(coordinator: GardenaBluetoothCoordinator) -> None:
    """Cancellation is never retried."""
    coordinator.client.read_char.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await coordinator._read_characteristic(Characteristic("test"))
    coordinator.client.read_char.assert_awaited_once()


async def test_hung_read(
    coordinator: GardenaBluetoothCoordinator, freezer: FrozenDateTimeFactory
) -> None:
    """The configured timeout cancels a read that never completes."""

    async def read_forever(char: Characteristic) -> None:
        freezer.tick(1)
        await asyncio.Event().wait()

    coordinator.client.read_char.side_effect = read_forever
    with (
        patch(
            "homeassistant.components.gardena_bluetooth.coordinator.READ_TIMEOUT", 0.001
        ),
        pytest.raises(UpdateFailed, match="after 2 attempts"),
    ):
        await coordinator._read_characteristic(Characteristic("test"))
    assert coordinator.client.read_char.await_count == 2


async def test_segmented_read_not_retried(
    coordinator: GardenaBluetoothCoordinator,
) -> None:
    """Segmented transfers keep their own timeout behavior."""
    coordinator.client.read_char.side_effect = TimeoutError
    char = Mock(spec=CharacteristicSegmented)
    with pytest.raises(TimeoutError):
        await coordinator._read_characteristic(char)
    coordinator.client.read_char.assert_awaited_once_with(char)
