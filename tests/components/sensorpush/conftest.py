"""SensorPush session fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from sensorpush_ble import SensorUpdate


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture(autouse=True)
def mock_async_poll() -> Generator[AsyncMock]:
    """Stop every advertisement from trying to connect to a real device.

    Any second generation SensorPush is due a battery poll the first time it is
    seen, so without this each injected advertisement would open a Bluetooth
    connection. Tests that care about polling set a return value on this mock.
    """
    with patch(
        "homeassistant.components.sensorpush.SensorPushBluetoothDeviceData.async_poll",
        AsyncMock(return_value=SensorUpdate(title=None, devices={})),
    ) as mock_poll:
        yield mock_poll
