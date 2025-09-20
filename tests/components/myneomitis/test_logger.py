"""Tests for logging output of myneomitis logger functions."""

import logging

import pytest

from homeassistant.components.myneomitis import logger


@pytest.mark.parametrize(
    ("func", "entity", "state", "expected"),
    [
        (
            logger.log_api_update,
            "Radiator1",
            {
                "currentTemp": 21.346,
                "overrideTemp": 22.5,
                "comfLimitMin": 7.0,
                "comfLimitMax": 28.0,
                "targetMode": "comfort",
                "consumption": "15.2kWh",
            },
            "MyNeomitis : API UPDATE - Radiator1 : "
            "currentTemp=21.35°C | overrideTemp=22.5°C | min=7.0°C | "
            "max=28.0°C | mode=comfort | consumption=15.2kWh",
        ),
        (
            logger.log_ws_update,
            "Radiator2",
            {
                "currentTemp": 20.0,
                "overrideTemp": 23.0,
                "targetMode": "eco",
            },
            "MyNeomitis : WS UPDATE - Radiator2 : "
            "currentTemp=20.00 | overrideTemp=23.0 | targetMode=eco",
        ),
        (
            logger.log_api_update_switch,
            "Switch1",
            {
                "targetMode": "auto",
                "relayMode": "manual",
                "systemPower": "on",
            },
            "MyNeomitis : API UPDATE - Switch1 : "
            "targetMode=auto | relayMode=manual | systemPower=on",
        ),
        (
            logger.log_ws_update_switch,
            "Switch2",
            {
                "targetMode": "off",
                "relayMode": "auto",
            },
            "MyNeomitis : WS UPDATE - Switch2 : targetMode=off | relayMode=auto",
        ),
        (
            logger.log_ws_update_ufh,
            "UFH1",
            {
                "changeOverUser": True,
                "changeOverOutput": False,
            },
            "MyNeomitis : WS UPDATE - UFH1 : "
            "changeOverUser=True | changeOverOutput=False",
        ),
    ],
)
def test_logging_output(
    func: callable,
    entity: str,
    state: dict,
    expected: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that each logger function outputs the expected message."""
    caplog.set_level(logging.INFO)
    func(entity, state)
    assert expected in caplog.text, f"Expected log not found: {expected}"
