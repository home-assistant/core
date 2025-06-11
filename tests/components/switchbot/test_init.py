"""Test the switchbot init."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant

from . import (
    HUBMINI_MATTER_SERVICE_INFO,
    LOCK_SERVICE_INFO,
    patch_async_ble_device_from_address,
)

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


async def test_setup_entry_without_ble_device(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup entry without ble device."""

    entry = mock_entry_factory("hygrometer_co2")
    entry.add_to_hass(hass)

    with patch_async_ble_device_from_address(None):
        await hass.config_entries.async_setup(entry.entry_id)

    assert (
        "Could not find Switchbot hygrometer_co2 with address aa:bb:cc:dd:ee:ff"
        in caplog.text
    )


async def test_coordinator_wait_ready_timeout(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the coordinator async_wait_ready timeout by calling it directly."""

    inject_bluetooth_service_info(hass, HUBMINI_MATTER_SERVICE_INFO)

    entry = mock_entry_factory("hubmini_matter")
    entry.add_to_hass(hass)

    timeout_mock = AsyncMock()
    timeout_mock.__aenter__.side_effect = TimeoutError
    timeout_mock.__aexit__.return_value = None

    with patch(
        "homeassistant.components.switchbot.coordinator.asyncio.timeout",
        return_value=timeout_mock,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    assert "aa:bb:cc:dd:ee:ff is not advertising state" in caplog.text
