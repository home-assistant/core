"""Test the switchbot init."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.switchbot.const import (
    CONF_CURTAIN_SPEED,
    CONF_RETRY_COUNT,
    DEFAULT_CURTAIN_SPEED,
    DEFAULT_RETRY_COUNT,
    DOMAIN,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_SENSOR_TYPE
from homeassistant.core import HomeAssistant

from . import (
    HUBMINI_MATTER_SERVICE_INFO,
    LOCK_SERVICE_INFO,
    WOCURTAIN_SERVICE_INFO,
    WOSENSORTH_SERVICE_INFO,
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
        await hass.async_block_till_done()
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
        await hass.async_block_till_done()

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
        await hass.async_block_till_done()

    assert "aa:bb:cc:dd:ee:ff is not advertising state" in caplog.text


@pytest.mark.parametrize(
    ("sensor_type", "service_info", "expected_options"),
    [
        (
            "curtain",
            WOCURTAIN_SERVICE_INFO,
            {
                CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT,
                CONF_CURTAIN_SPEED: DEFAULT_CURTAIN_SPEED,
            },
        ),
        (
            "hygrometer",
            WOSENSORTH_SERVICE_INFO,
            {
                CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT,
            },
        ),
    ],
)
async def test_migrate_entry_from_v1_1_to_v1_2(
    hass: HomeAssistant,
    sensor_type: str,
    service_info,
    expected_options: dict,
) -> None:
    """Test migration from version 1.1 to 1.2 adds default options."""
    inject_bluetooth_service_info(hass, service_info)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: sensor_type,
        },
        unique_id="aabbccddeeff",
        version=1,
        minor_version=1,
        options={},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.options == expected_options


async def test_migrate_entry_preserves_existing_options(
    hass: HomeAssistant,
) -> None:
    """Test migration preserves existing options."""
    inject_bluetooth_service_info(hass, WOCURTAIN_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "curtain",
        },
        unique_id="aabbccddeeff",
        version=1,
        minor_version=1,
        options={CONF_RETRY_COUNT: 5},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 1
    assert entry.minor_version == 2
    # Existing retry_count should be preserved, curtain_speed added
    assert entry.options[CONF_RETRY_COUNT] == 5
    assert entry.options[CONF_CURTAIN_SPEED] == DEFAULT_CURTAIN_SPEED


async def test_migrate_entry_fails_for_future_version(
    hass: HomeAssistant,
) -> None:
    """Test migration fails for future versions."""
    inject_bluetooth_service_info(hass, WOCURTAIN_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "curtain",
        },
        unique_id="aabbccddeeff",
        version=2,
        minor_version=1,
        options={},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Entry should not be loaded due to failed migration
    assert entry.version == 2
    assert entry.minor_version == 1
