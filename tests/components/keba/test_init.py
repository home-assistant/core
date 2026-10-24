"""Tests for setting up the KEBA charging station integration.

These pin the behaviour of the YAML integration as it ships with
keba-kecontact 1.3.0, including behaviour that looks wrong. Tests named
``..._currently_...`` describe such behaviour.
"""

from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.keba import KebaHandler
from homeassistant.components.keba.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import (
    HOST,
    UDP_PORT,
    FakeKebaStation,
    async_advance,
    async_seconds_until_poll,
    async_settle,
    stop_polling,
)

REPORTS = ["report 1", "report 2", "report 3", "report 100"]


async def test_setup_connects_and_requests_all_reports(
    hass: HomeAssistant, setup_keba: FakeKebaStation
) -> None:
    """Test setup binds UDP 7090, probes report 1, then requests every report."""
    station = setup_keba

    assert station.local_addr == ("0.0.0.0", UDP_PORT)
    assert station.remote_addr == (HOST, UDP_PORT)
    # Library probe, then the integration's own initial request.
    assert station.sent[:5] == ["report 1", *REPORTS]
    assert hass.services.has_service(DOMAIN, "request_data")
    assert hass.states.get("sensor.keba_p30_charging_power") is not None


async def test_setup_disables_failsafe_by_default(
    hass: HomeAssistant, setup_keba: FakeKebaStation
) -> None:
    """Test setup switches failsafe off when it is not configured."""
    assert setup_keba.commands == ["failsafe 0 0 0"]


@pytest.mark.parametrize(
    "keba_config",
    [
        {
            DOMAIN: {
                "host": HOST,
                "failsafe": True,
                "failsafe_timeout": 60,
                "failsafe_fallback": 10,
                "failsafe_persist": 1,
            }
        }
    ],
)
async def test_setup_applies_configured_failsafe(
    hass: HomeAssistant, setup_keba: FakeKebaStation
) -> None:
    """Test setup sends the configured failsafe values."""
    assert setup_keba.commands == ["failsafe 60 10000 1"]


async def test_setup_failsafe_out_of_range_currently_unchecked(
    hass: HomeAssistant, station: FakeKebaStation
) -> None:
    """Test an out-of-range failsafe timeout is passed on unchecked.

    The integration starts set_failsafe in a task and does not validate the
    timeout itself. The library rejects 5 with ValueError, but inside that
    task, so the try/except around starting it never sees the error, and no
    failsafe command is sent.
    """
    with patch.object(KebaHandler, "set_failsafe") as set_failsafe:
        assert await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: {"host": HOST, "failsafe": True, "failsafe_timeout": 5}},
        )
        await async_settle(hass)

    set_failsafe.assert_awaited_once_with(5, 6, 0)

    await stop_polling(hass)


async def test_setup_silent_station_currently_raises(
    hass: HomeAssistant,
    station: FakeKebaStation,
    freezer: FrozenDateTimeFactory,
    keba_config: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a station that never answers fails setup with an unhandled error.

    The library raises ConnectionError when report 1 brings no Product. The
    integration does not catch it, so its own "Could not find a charging
    station" message is not logged.
    """
    station.silent = True

    assert not await async_setup_component(hass, DOMAIN, keba_config)
    await hass.async_block_till_done()

    assert station.sent == ["report 1"]
    assert "Error during setup of component keba" in caplog.text
    assert "Could not connect to Keba charging station" in caplog.text
    assert "Could not find a charging station" not in caplog.text
    await async_advance(hass, freezer, 60)
    assert station.sent == ["report 1"]


async def test_setup_without_serial(
    hass: HomeAssistant,
    station: FakeKebaStation,
    freezer: FrozenDateTimeFactory,
    keba_config: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a station that reports a product but no serial number."""
    for report in station.reports.values():
        report.pop("Serial", None)

    assert not await async_setup_component(hass, DOMAIN, keba_config)
    await hass.async_block_till_done()

    assert f"Could not find a charging station at {HOST}" in caplog.text
    assert station.commands == []
    assert not hass.services.has_service(DOMAIN, "request_data")
    sent = list(station.sent)
    await async_advance(hass, freezer, 60)
    assert station.sent == sent


async def test_polls_every_refresh_interval(
    hass: HomeAssistant, setup_keba: FakeKebaStation, freezer: FrozenDateTimeFactory
) -> None:
    """Test the polling loop requests every report, every 5 seconds."""
    station = setup_keba
    sent_before = len(station.sent)

    assert await async_seconds_until_poll(hass, freezer, station) == 5
    assert station.sent[sent_before:] == REPORTS
    assert await async_seconds_until_poll(hass, freezer, station) == 5


@pytest.mark.parametrize(
    ("refresh_interval", "expected_delay"),
    [(2, 5), (5, 5), (30, 30)],
)
async def test_refresh_interval_has_a_floor(
    hass: HomeAssistant,
    station: FakeKebaStation,
    freezer: FrozenDateTimeFactory,
    refresh_interval: int,
    expected_delay: int,
) -> None:
    """Test the polling interval is the configured one, but never under 5 seconds."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"host": HOST, "refresh_interval": refresh_interval}}
    )
    await async_settle(hass)

    assert await async_seconds_until_poll(hass, freezer, station) == expected_delay

    await stop_polling(hass)


async def test_command_switches_to_fast_polling(
    hass: HomeAssistant, setup_keba: FakeKebaStation, freezer: FrozenDateTimeFactory
) -> None:
    """Test a command polls at once, then four times 2 seconds apart, then every 5."""
    station = setup_keba
    sent_before = len(station.sent)

    await hass.services.async_call(DOMAIN, "enable", blocking=True)
    await async_settle(hass)

    assert station.sent[sent_before:] == ["ena 1", *REPORTS]
    assert [
        await async_seconds_until_poll(hass, freezer, station) for _ in range(5)
    ] == [2, 2, 2, 2, 5]
