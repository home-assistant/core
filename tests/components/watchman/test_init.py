"""Test Kingspan Watchman SENSiT setup process."""

import logging
from unittest.mock import AsyncMock, patch

from connectsensor.exceptions import (
    KingspanAPIError,
    KingspanErrorCode,
    KingspanInvalidCredentialsError,
    KingspanNoDataError,
    KingspanTimeoutError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.watchman import (
    SENSiTDataUpdateCoordinator,
    async_remove_config_entry_device,
)
from homeassistant.components.watchman.const import CONF_USAGE_WINDOW, DOMAIN
from homeassistant.components.watchman.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import MOCK_CONFIG, MOCK_TANK_LEVEL, MOCK_TANK_SERIAL_NUMBER, HistoryType


async def test_setup_unload_and_reload_entry(
    hass: HomeAssistant, mock_sensor_client
) -> None:
    """Test entry setup and unload state transitions."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert isinstance(config_entry.runtime_data, SENSiTDataUpdateCoordinator)

    # Reload the entry and assert it remains loaded
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.LOADED

    # Unload the entry via the core HA manager to properly alter the state
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_options_update_triggers_reload(
    hass: HomeAssistant, mock_sensor_client
) -> None:
    """Test that changing integration options reloads the entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Patch the underlying reload call to verify the listener fired it
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_async_reload:
        hass.config_entries.async_update_entry(
            config_entry, options={CONF_USAGE_WINDOW: 30}
        )
        await hass.async_block_till_done()

        mock_async_reload.assert_called_once_with(config_entry.entry_id)


async def test_auth_missing(hass: HomeAssistant, mock_sensor_client) -> None:
    """Test entry setup and unload."""
    # Create a mock entry so we don't have to go through config flow
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={"username": None}, entry_id="test"
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_ERROR
    assert config_entry.entry_id not in hass.data.get(DOMAIN, {})
    assert config_entry.error_reason_translation_key == "credentials_not_set"
    assert DOMAIN not in hass.data


@pytest.mark.parametrize(
    (
        "mock_sensor_client",
        "log_level",
        "expected_state",
        "expected_log",
        "attr_name",
        "attr_value",
        "expect_repair_issue",
    ),
    [
        (
            {"exception": KingspanInvalidCredentialsError("test bad auth")},
            logging.WARNING,
            ConfigEntryState.SETUP_ERROR,
            None,
            "error_reason_translation_key",
            "credentials_invalid",
            True,
        ),
        (
            {"exception": KingspanTimeoutError("test timeout")},
            logging.WARNING,
            ConfigEntryState.SETUP_RETRY,
            "Error communicating with Kingspan API: test timeout",
            "reason",
            "Timed out while connecting to the Kingspan service",
            False,
        ),
        (
            {"exception": KingspanNoDataError("no level data")},
            logging.WARNING,
            ConfigEntryState.SETUP_RETRY,
            "No data available for username 'test@example.com'",
            None,
            None,
            False,
        ),
    ],
    indirect=["mock_sensor_client"],
)
async def test_setup_auth_failures(
    hass: HomeAssistant,
    mock_sensor_client,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
    log_level,
    expected_state,
    expected_log,
    attr_name,
    attr_value,
    expect_repair_issue,
) -> None:
    """Test entry setup handles authentication and connection failures cleanly."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    with caplog.at_level(log_level):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == expected_state
    assert config_entry.entry_id not in hass.data.get(DOMAIN, {})

    if expected_log:
        assert expected_log in caplog.text

    if attr_name:
        assert getattr(config_entry, attr_name) == attr_value

    if expect_repair_issue:
        issue = issue_registry.async_get_issue(
            DOMAIN, f"credentials_{config_entry.entry_id}"
        )
        assert issue is not None
        assert issue.is_fixable is True


@pytest.mark.parametrize("mock_sensor_client", [{"num_tanks": 0}], indirect=True)
async def test_setup_entry_no_data_return_false(
    hass: HomeAssistant, mock_sensor_client
) -> None:
    """Test setup exits cleanly when a valid login finds an empty tank list."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY
    assert config_entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_runtime_data_fallback_and_unload(
    hass: HomeAssistant, mock_sensor_client
) -> None:
    """Runtime data should be stored on the entry and cleaned up on unload."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diagnostics["tank_count"] == 1
    assert config_entry.runtime_data is not None

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.entry_id not in hass.data.get(DOMAIN, {})


@pytest.mark.parametrize(
    "exception",
    [
        KingspanAPIError("api-test error", KingspanErrorCode.CANNOT_CONNECT),
        KingspanTimeoutError("connection timeout"),
    ],
)
async def test_coordinator_logs_available_again(
    hass: HomeAssistant, mock_sensor_client, caplog: pytest.LogCaptureFixture, exception
) -> None:
    """Coordinator should log a recovery message after a previously failed refresh."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data
    caplog.set_level(logging.INFO)
    caplog.clear()

    # Scope the failure patch tightly so recovery correctly reverts to the original working mock
    with patch(
        "homeassistant.components.watchman.coordinator.AsyncSensorClient"
    ) as mock_class:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.login.side_effect = exception
        mock_class.return_value = mock_instance

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    warnings = [
        record
        for record in caplog.records
        if "Error communicating with Kingspan API" in record.message
    ]
    assert len(warnings) == 1
    assert coordinator._unavailable_logged is True

    # Call again with the patch disabled to test recovery mode
    await coordinator._async_update_data()

    assert "Kingspan service is available again" in caplog.text
    assert coordinator._unavailable_logged is False


@pytest.mark.parametrize(
    "mock_sensor_client",
    [
        {
            "tank_level": MOCK_TANK_LEVEL,
            "history_type": HistoryType.DECREASING,
            "num_tanks": 2,
        }
    ],
    indirect=True,
)
async def test_diagnostics(hass: HomeAssistant, mock_sensor_client) -> None:
    """Test generating diagnostic data."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    assert diagnostics["config_entry_data"]["username"] == "**REDACTED**"
    assert diagnostics["config_entry_data"]["password"] == "**REDACTED**"
    assert diagnostics["tank_count"] == 2
    assert len(diagnostics["tanks"]) == 2
    assert diagnostics["last_update_success"]
    assert diagnostics["tanks"][0]["serial_number"] == "**REDACTED**"
    assert diagnostics["tanks"][0]["level"] == 1000


async def test_remove_stale_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, mock_sensor_client
) -> None:
    """Test removing a stale device is allowed, but active devices are rejected."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    stale_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "old_stale_serial")},
    )
    assert (
        await async_remove_config_entry_device(hass, config_entry, stale_device) is True
    )

    active_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, MOCK_TANK_SERIAL_NUMBER)},
    )
    assert (
        await async_remove_config_entry_device(hass, config_entry, active_device)
        is False
    )
