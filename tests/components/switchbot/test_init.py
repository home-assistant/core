"""Test the switchbot init."""

from collections.abc import Callable
from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant

from . import LOCK_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            ValueError("wrong model"),
            "Switchbot device initialization failed because of incorrect configuration parameters: wrong model",
        ),
    ],
)
async def test_exception_handling_for_device_initialization(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    exception: Exception,
    error_message: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test exception handling for lock initialization."""
    inject_bluetooth_service_info(hass, LOCK_SERVICE_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="lock")
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.switchbot.lock.switchbot.SwitchbotLock.__init__",
        side_effect=exception,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert error_message in caplog.text
