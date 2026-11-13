"""Tests for the KEBA charging station actions.

Each action is pinned to the exact library call it makes today, argument
types included: values reach keba-kecontact as floats and bools, which it
formats into its UDP commands as-is. Tests named ``..._currently_...`` pin
that and other suspect behaviour.
"""

from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.keba.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import HOST, POLL_INTERVAL, async_seconds_until_poll, async_settle


@pytest.mark.parametrize(
    ("service", "data", "method", "args"),
    [
        ("set_energy", {"energy": 10}, "set_energy", (10.0,)),
        ("set_energy", {"energy": 0}, "set_energy", (0.0,)),
        ("set_current", {"current": 16}, "set_current", (16.0,)),
        ("set_current", {"current": 6.5}, "set_current", (6.5,)),
        ("authorize", {}, "start", ("00845500",)),
        ("deauthorize", {}, "stop", ("00845500",)),
        ("enable", {}, "enable", (True,)),
        ("disable", {}, "enable", (False,)),
    ],
)
async def test_service_calls_library(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    service: str,
    data: dict[str, Any],
    method: str,
    args: tuple[Any, ...],
) -> None:
    """Test each action makes its library call, with these argument types."""
    await hass.services.async_call(DOMAIN, service, data, blocking=True)

    mock = getattr(setup_keba, method)
    mock.assert_awaited_once_with(*args)
    assert [type(arg) for arg in mock.await_args.args] == [type(arg) for arg in args]


@pytest.mark.parametrize("keba_config", [{DOMAIN: {"host": HOST, "rfid": "1234ABCD"}}])
@pytest.mark.parametrize(
    ("service", "method"), [("authorize", "start"), ("deauthorize", "stop")]
)
async def test_authorization_uses_configured_rfid(
    hass: HomeAssistant, setup_keba: MagicMock, service: str, method: str
) -> None:
    """Test authorize and deauthorize use the RFID tag from the configuration."""
    await hass.services.async_call(DOMAIN, service, blocking=True)

    getattr(setup_keba, method).assert_awaited_once_with("1234ABCD")


@pytest.mark.parametrize("persist", [0, 1])
async def test_set_failsafe_currently_passes_float_and_bool(
    hass: HomeAssistant, setup_keba: MagicMock, persist: int
) -> None:
    """Test set_failsafe converts the fallback to float and persist to bool.

    keba-kecontact 1.3.0 formats both with str(), so the station is sent
    "failsafe 30 6000.0 True" rather than "failsafe 30 6000 1". The failsafe
    applied at startup passes the configured ints unchanged.
    """
    setup_keba.set_failsafe.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        "set_failsafe",
        {"failsafe_timeout": 30, "failsafe_fallback": 6, "failsafe_persist": persist},
        blocking=True,
    )

    setup_keba.set_failsafe.assert_awaited_once_with(30, 6.0, bool(persist))
    assert [type(arg) for arg in setup_keba.set_failsafe.await_args.args] == [
        int,
        float,
        bool,
    ]


async def test_request_data_requests_data_without_fast_polling(
    hass: HomeAssistant, setup_keba: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test request_data asks the library for data and does not start fast polling."""
    polls_before = setup_keba.request_data.await_count

    await hass.services.async_call(DOMAIN, "request_data", blocking=True)

    assert setup_keba.request_data.await_count == polls_before + 1
    assert await async_seconds_until_poll(hass, freezer, setup_keba) == POLL_INTERVAL


async def test_set_current_without_fast_polling(
    hass: HomeAssistant, setup_keba: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test set_current leaves the polling interval alone."""
    await hass.services.async_call(
        DOMAIN, "set_current", {"current": 16}, blocking=True
    )
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
    setup_keba: MagicMock,
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
        ("set_current", {}, "Current value is not correct"),
        ("set_current", {"current": "max"}, "Current value is not correct"),
        ("set_failsafe", {}, "Values are not correct for"),
        (
            "set_failsafe",
            {"failsafe_timeout": "x", "failsafe_fallback": 6, "failsafe_persist": 0},
            "Values are not correct for",
        ),
    ],
)
async def test_invalid_values_are_logged_not_raised(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    caplog: pytest.LogCaptureFixture,
    service: str,
    data: dict[str, Any],
    message: str,
) -> None:
    """Test missing or non-numeric values only log a warning and call nothing.

    The actions have no schema, so bad input is caught inside the handler and
    the call still succeeds.
    """
    setup_keba.set_failsafe.reset_mock()

    await hass.services.async_call(DOMAIN, service, data, blocking=True)

    getattr(setup_keba, service).assert_not_awaited()
    assert message in caplog.text


@pytest.mark.parametrize(
    ("service", "data", "message"),
    [
        ("set_energy", {"energy": 0.5}, "Energy value is not correct"),
        ("set_current", {"current": 63}, "Current value is not correct"),
        (
            "set_failsafe",
            {"failsafe_timeout": 5, "failsafe_fallback": 6, "failsafe_persist": 0},
            "Values are not correct for",
        ),
    ],
)
async def test_library_rejection_is_logged_not_raised(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    service: str,
    data: dict[str, Any],
    message: str,
) -> None:
    """Test a value the library rejects only logs a warning, without fast polling.

    The integration does no range checks of its own. keba-kecontact 1.3.0
    rejects these values with ValueError; set_current 63 among them, although
    services.yaml allows up to 63.
    """
    getattr(setup_keba, service).side_effect = ValueError("rejected by the library")

    await hass.services.async_call(DOMAIN, service, data, blocking=True)
    await async_settle(hass)

    assert message in caplog.text
    assert await async_seconds_until_poll(hass, freezer, setup_keba) == POLL_INTERVAL
