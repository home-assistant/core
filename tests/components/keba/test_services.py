"""Tests for the KEBA charging station actions.

Each action is pinned to the exact UDP command it sends today. Values reach
the library as floats, so several commands carry a ".0" the station has to
parse; tests named ``..._currently_...`` pin that and other suspect behaviour.
"""

from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.keba.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import (
    HOST,
    POLL_INTERVAL,
    FakeKebaStation,
    async_seconds_until_poll,
    async_settle,
)


@pytest.mark.parametrize(
    ("service", "data", "command"),
    [
        ("set_energy", {"energy": 10}, "setenergy 100000.0"),
        ("set_energy", {"energy": 0}, "setenergy 0.0"),
        ("set_current", {"current": 16}, "currtime 16000.0 1"),
        ("set_current", {"current": 6.5}, "currtime 6500.0 1"),
        ("authorize", {}, "start 00845500 01010400000000000000"),
        ("deauthorize", {}, "stop 00845500"),
        ("enable", {}, "ena 1"),
        ("disable", {}, "ena 0"),
    ],
)
async def test_service_sends_command(
    hass: HomeAssistant,
    setup_keba: FakeKebaStation,
    service: str,
    data: dict[str, Any],
    command: str,
) -> None:
    """Test each action sends its command to the station."""
    await hass.services.async_call(DOMAIN, service, data, blocking=True)

    assert setup_keba.commands[1:] == [command]


@pytest.mark.parametrize("keba_config", [{DOMAIN: {"host": HOST, "rfid": "1234ABCD"}}])
@pytest.mark.parametrize(
    ("service", "command"),
    [
        ("authorize", "start 1234ABCD 01010400000000000000"),
        ("deauthorize", "stop 1234ABCD"),
    ],
)
async def test_authorization_uses_configured_rfid(
    hass: HomeAssistant, setup_keba: FakeKebaStation, service: str, command: str
) -> None:
    """Test authorize and deauthorize use the RFID tag from the configuration."""
    await hass.services.async_call(DOMAIN, service, blocking=True)

    assert setup_keba.commands[1:] == [command]


@pytest.mark.parametrize(
    ("persist", "command"),
    [
        (0, "failsafe 30 6000.0 False"),
        (1, "failsafe 30 6000.0 True"),
    ],
)
async def test_set_failsafe_currently_sends_python_bool(
    hass: HomeAssistant, setup_keba: FakeKebaStation, persist: int, command: str
) -> None:
    """Test set_failsafe sends the persist flag as 'True'/'False', not 1/0.

    The integration converts persist with bool() and the fallback with
    float(); the library formats both with str(). Startup failsafe, which
    passes ints, sends "failsafe 30 6000 1" instead.
    """
    await hass.services.async_call(
        DOMAIN,
        "set_failsafe",
        {"failsafe_timeout": 30, "failsafe_fallback": 6, "failsafe_persist": persist},
        blocking=True,
    )

    assert setup_keba.commands[1:] == [command]


async def test_request_data_requests_all_reports(
    hass: HomeAssistant, setup_keba: FakeKebaStation, freezer: FrozenDateTimeFactory
) -> None:
    """Test request_data requests every report and does not start fast polling."""
    station = setup_keba
    sent_before = len(station.sent)

    await hass.services.async_call(DOMAIN, "request_data", blocking=True)

    assert station.sent[sent_before:] == [
        "report 1",
        "report 2",
        "report 3",
        "report 100",
    ]
    assert await async_seconds_until_poll(hass, freezer, setup_keba) == POLL_INTERVAL


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("set_current", {"current": 16}),
        ("request_data", {}),
    ],
)
async def test_service_without_fast_polling(
    hass: HomeAssistant,
    setup_keba: FakeKebaStation,
    freezer: FrozenDateTimeFactory,
    service: str,
    data: dict[str, Any],
) -> None:
    """Test set_current and request_data leave the polling interval alone."""
    await hass.services.async_call(DOMAIN, service, data, blocking=True)
    await hass.async_block_till_done()

    assert await async_seconds_until_poll(hass, freezer, setup_keba) == POLL_INTERVAL


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("set_energy", {"energy": 10}),
        ("authorize", {}),
        ("deauthorize", {}),
        ("enable", {}),
        ("disable", {}),
        (
            "set_failsafe",
            {"failsafe_timeout": 30, "failsafe_fallback": 6, "failsafe_persist": 0},
        ),
    ],
)
async def test_service_with_fast_polling(
    hass: HomeAssistant,
    setup_keba: FakeKebaStation,
    freezer: FrozenDateTimeFactory,
    service: str,
    data: dict[str, Any],
) -> None:
    """Test the other actions switch the polling loop to 2-second polls."""
    await hass.services.async_call(DOMAIN, service, data, blocking=True)
    await async_settle(hass)

    assert await async_seconds_until_poll(hass, freezer, setup_keba) == 2


@pytest.mark.parametrize(
    ("service", "data", "message"),
    [
        ("set_energy", {}, "Energy value is not correct"),
        ("set_energy", {"energy": "lots"}, "Energy value is not correct"),
        ("set_energy", {"energy": 0.5}, "Energy value is not correct"),
        ("set_current", {}, "Current value is not correct"),
        ("set_current", {"current": 5}, "Current value is not correct"),
        ("set_current", {"current": 63}, "Current value is not correct"),
        (
            "set_failsafe",
            {"failsafe_timeout": 5, "failsafe_fallback": 6, "failsafe_persist": 0},
            "Values are not correct for",
        ),
        ("set_failsafe", {}, "Values are not correct for"),
    ],
)
async def test_invalid_values_are_logged_not_raised(
    hass: HomeAssistant,
    setup_keba: FakeKebaStation,
    caplog: pytest.LogCaptureFixture,
    service: str,
    data: dict[str, Any],
    message: str,
) -> None:
    """Test rejected values only log a warning and send nothing.

    The actions have no schema, so bad input is caught inside the handler and
    the call still succeeds. set_current 63 is rejected by the library even
    though services.yaml allows up to 63.
    """
    await hass.services.async_call(DOMAIN, service, data, blocking=True)

    assert setup_keba.commands[1:] == []
    assert message in caplog.text
