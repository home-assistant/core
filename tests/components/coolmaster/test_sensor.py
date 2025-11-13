"""The test for the Coolmaster sensor platform."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from homeassistant.components.coolmaster.const import MAX_RETRIES
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity


async def test_sensor(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster sensor."""
    assert hass.states.get("sensor.l1_100_error_code").state == "OK"
    assert hass.states.get("sensor.l1_101_error_code").state == "Err1"


async def test_retry_with_no_error(
    hass: HomeAssistant,
    config_entry_with_errors: ConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test without errors."""

    caplog.set_level(logging.DEBUG, logger="homeassistant.components.coolmaster")

    with patch(
        "tests.components.coolmaster.conftest.CoolMasterNetErrorMock.status",
        wraps=config_entry_with_errors.runtime_data._coolmaster.status,
    ) as mock_status:
        config_entry_with_errors.runtime_data._coolmaster._fail_count = 0
        await async_update_entity(hass, "sensor.l1_101_error_code")
        await hass.async_block_till_done()

        assert mock_status.call_count == 1
        debugs, errors = count_logs(caplog.records)
        assert debugs == 0
        assert errors == 0


@patch("homeassistant.components.coolmaster.coordinator.BACKOFF_BASE_DELAY", new=0)
async def test_retry_with_less_than_max_errors(
    hass: HomeAssistant,
    config_entry_with_errors: ConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test MAX_RETRIES-1 errors."""

    caplog.set_level(logging.DEBUG, logger="homeassistant.components.coolmaster")

    with patch(
        "tests.components.coolmaster.conftest.CoolMasterNetErrorMock.status",
        wraps=config_entry_with_errors.runtime_data._coolmaster.status,
    ) as mock_status:
        config_entry_with_errors.runtime_data._coolmaster._fail_count = MAX_RETRIES - 1
        await async_update_entity(hass, "sensor.l1_101_error_code")
        await hass.async_block_till_done()

        assert mock_status.call_count == MAX_RETRIES  # The last try succeeds
        debugs, errors = count_logs(caplog.records)
        assert errors == 0
        assert debugs == MAX_RETRIES - 1


@patch("homeassistant.components.coolmaster.coordinator.BACKOFF_BASE_DELAY", new=0)
async def test_retry_with_more_than_max_errors(
    hass: HomeAssistant,
    config_entry_with_errors: ConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test MAX_RETRIES+1 errors."""

    caplog.set_level(logging.DEBUG, logger="homeassistant.components.coolmaster")

    with patch(
        "tests.components.coolmaster.conftest.CoolMasterNetErrorMock.status",
        wraps=config_entry_with_errors.runtime_data._coolmaster.status,
    ) as mock_status:
        config_entry_with_errors.runtime_data._coolmaster._fail_count = MAX_RETRIES + 1
        await async_update_entity(hass, "sensor.l1_101_error_code")
        await hass.async_block_till_done()

        assert (
            mock_status.call_count == MAX_RETRIES
        )  # The retries are capped at MAX_RETRIES
        debugs, errors = count_logs(caplog.records)
        assert errors == 1
        assert debugs == MAX_RETRIES - 1


@patch("homeassistant.components.coolmaster.coordinator.BACKOFF_BASE_DELAY", new=0)
async def test_retry_with_empty_status(
    hass: HomeAssistant,
    config_entry_with_empty_status: ConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test empty status response."""

    caplog.set_level(logging.DEBUG, logger="homeassistant.components.coolmaster")

    with patch(
        "tests.components.coolmaster.conftest.CoolMasterNetEmptyStatusMock.status",
        wraps=config_entry_with_empty_status.runtime_data._coolmaster.status,
    ) as mock_status:
        await async_update_entity(hass, "sensor.l1_101_error_code")
        await hass.async_block_till_done()

        assert (
            mock_status.call_count == MAX_RETRIES
        )  # The retries are capped at MAX_RETRIES
        debugs, errors = count_logs(caplog.records)
        assert errors == 1
        assert debugs == MAX_RETRIES


def count_logs(log_records: list[logging.LogRecord]) -> tuple[int, int]:
    """Count the number of log records."""
    debug_logs = [
        rec
        for rec in log_records
        if rec.levelno == logging.DEBUG
        and "Error communicating with coolmaster" in rec.getMessage()
    ]

    error_logs = [
        rec
        for rec in log_records
        if rec.levelno == logging.ERROR
        and "Error fetching coolmaster data" in rec.getMessage()
    ]
    return len(debug_logs), len(error_logs)
