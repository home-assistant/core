"""Tests for logging output of myneomitis logger functions."""

import logging

import pytest

from homeassistant.components.myneomitis import logger


def test_log_ws_update(caplog: pytest.LogCaptureFixture) -> None:
    """Test that log_ws_update outputs the expected debug message."""
    caplog.set_level(logging.DEBUG)

    state = {
        "currentTemp": 21.5,
        "targetMode": 1,
    }

    logger.log_ws_update("Radiator Salon", state)

    assert "WebSocket update for Radiator Salon" in caplog.text
    assert "temp=21.5°C" in caplog.text
    assert "mode=1" in caplog.text


def test_log_ws_update_missing_fields(caplog: pytest.LogCaptureFixture) -> None:
    """Test log_ws_update with missing state fields."""
    caplog.set_level(logging.DEBUG)

    state = {}

    logger.log_ws_update("Test Device", state)

    assert "WebSocket update for Test Device" in caplog.text
    assert "temp=-1" in caplog.text  # Default value
    assert "mode=N/A" in caplog.text  # Default value
