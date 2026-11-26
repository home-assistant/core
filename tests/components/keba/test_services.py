"""Tests for the KEBA charging station actions."""

from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.keba.const import DOMAIN, KebaService, KebaServiceArgument
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .conftest import HOST, async_seconds_until_poll, async_settle

FAILSAFE = {
    KebaServiceArgument.FAILSAFE_TIMEOUT: 30,
    KebaServiceArgument.FAILSAFE_FALLBACK: 6,
    KebaServiceArgument.FAILSAFE_PERSIST: 1,
}


@pytest.mark.parametrize(
    ("service", "data", "method", "args", "next_poll"),
    [
        (
            KebaService.SET_ENERGY,
            {KebaServiceArgument.ENERGY: 10},
            "set_energy",
            (10.0,),
            2,
        ),
        (
            KebaService.SET_CURRENT,
            {KebaServiceArgument.CURRENT: 16},
            "set_current",
            (16.0,),
            5,
        ),
        (KebaService.AUTHORIZE, {}, "start", ("00845500",), 2),
        (KebaService.DEAUTHORIZE, {}, "stop", ("00845500",), 2),
        (KebaService.ENABLE, {}, "enable", (True,), 2),
        (KebaService.DISABLE, {}, "enable", (False,), 2),
        (KebaService.SET_FAILSAFE, FAILSAFE, "set_failsafe", (30, 6.0, True), 2),
    ],
)
async def test_action(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    freezer: FrozenDateTimeFactory,
    service: KebaService,
    data: dict[str, Any],
    method: str,
    args: tuple[Any, ...],
    next_poll: int,
) -> None:
    """Test each action's library call, its argument types, and the next poll."""
    mock = getattr(setup_keba, method)
    mock.reset_mock()

    await hass.services.async_call(DOMAIN, service, data, blocking=True)
    await async_settle(hass)

    mock.assert_awaited_once_with(*args)
    assert [type(arg) for arg in mock.await_args.args] == [type(arg) for arg in args]
    assert await async_seconds_until_poll(hass, freezer, setup_keba) == next_poll


@pytest.mark.parametrize(
    "keba_config", [{DOMAIN: {CONF_HOST: HOST, "rfid": "1234ABCD"}}]
)
@pytest.mark.parametrize(
    ("service", "method"),
    [(KebaService.AUTHORIZE, "start"), (KebaService.DEAUTHORIZE, "stop")],
)
async def test_authorization_uses_configured_rfid(
    hass: HomeAssistant, setup_keba: MagicMock, service: KebaService, method: str
) -> None:
    """Test authorize and deauthorize send the configured RFID tag."""
    await hass.services.async_call(DOMAIN, service, blocking=True)

    getattr(setup_keba, method).assert_awaited_once_with("1234ABCD")


async def test_request_data(
    hass: HomeAssistant, setup_keba: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test request_data polls once, and leaves the polling interval alone."""
    polls_before = setup_keba.request_data.await_count

    await hass.services.async_call(DOMAIN, KebaService.REQUEST_DATA, blocking=True)

    assert setup_keba.request_data.await_count == polls_before + 1
    assert await async_seconds_until_poll(hass, freezer, setup_keba) == 5


@pytest.mark.parametrize(
    ("service", "data", "method", "message"),
    [
        (KebaService.SET_ENERGY, {}, "set_energy", "Energy value is not correct"),
        (
            KebaService.SET_ENERGY,
            {KebaServiceArgument.ENERGY: "lots"},
            "set_energy",
            "Energy value is not correct",
        ),
        (KebaService.SET_CURRENT, {}, "set_current", "Current value is not correct"),
        (
            KebaService.SET_CURRENT,
            {KebaServiceArgument.CURRENT: "max"},
            "set_current",
            "Current value is not correct",
        ),
        (KebaService.SET_FAILSAFE, {}, "set_failsafe", "Values are not correct for"),
        (
            KebaService.SET_FAILSAFE,
            {**FAILSAFE, KebaServiceArgument.FAILSAFE_TIMEOUT: "x"},
            "set_failsafe",
            "Values are not correct for",
        ),
    ],
)
async def test_invalid_value_is_logged(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    caplog: pytest.LogCaptureFixture,
    service: KebaService,
    data: dict[str, Any],
    method: str,
    message: str,
) -> None:
    """Test a missing or non-numeric value logs a warning and calls nothing."""
    mock = getattr(setup_keba, method)
    mock.reset_mock()

    await hass.services.async_call(DOMAIN, service, data, blocking=True)

    mock.assert_not_awaited()
    assert message in caplog.text


@pytest.mark.parametrize(
    ("service", "data", "method", "message"),
    [
        (
            KebaService.SET_ENERGY,
            {KebaServiceArgument.ENERGY: 0.5},
            "set_energy",
            "Energy value is not correct",
        ),
        (
            KebaService.SET_CURRENT,
            {KebaServiceArgument.CURRENT: 63},
            "set_current",
            "Current value is not correct",
        ),
        (
            KebaService.SET_FAILSAFE,
            {**FAILSAFE, KebaServiceArgument.FAILSAFE_TIMEOUT: 5},
            "set_failsafe",
            "Values are not correct for",
        ),
    ],
)
async def test_library_rejection_is_logged(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    service: KebaService,
    data: dict[str, Any],
    method: str,
    message: str,
) -> None:
    """Test a value the library rejects logs a warning, without fast polling."""
    getattr(setup_keba, method).side_effect = ValueError("rejected by the library")

    await hass.services.async_call(DOMAIN, service, data, blocking=True)
    await async_settle(hass)

    assert message in caplog.text
    assert await async_seconds_until_poll(hass, freezer, setup_keba) == 5
