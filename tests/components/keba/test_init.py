"""Tests for setting up the KEBA charging station integration.

These pin the behaviour of the YAML integration as it ships with
keba-kecontact 1.3.0, including behaviour that looks wrong. Tests named
``..._currently_...`` describe such behaviour.
"""

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.keba.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import HOST, UDP_PORT, FakeKebaStation, PollClock, stop_polling

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


async def test_setup_failsafe_out_of_range_currently_unhandled(
    hass: HomeAssistant,
    station: FakeKebaStation,
    poll_clock: PollClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an out-of-range failsafe timeout ends in an unhandled task error.

    The library raises ValueError inside a task created with
    hass.loop.create_task, so the try/except around the create_task call
    never sees it and the integration's warning is never logged.
    """
    created: list[asyncio.Task[Any]] = []
    create_task = hass.loop.create_task

    def spy(coro: Any, **kwargs: Any) -> asyncio.Task[Any]:
        task = create_task(coro, **kwargs)
        created.append(task)
        return task

    with patch.object(hass.loop, "create_task", spy):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: {"host": HOST, "failsafe": True, "failsafe_timeout": 5}},
        )
        await hass.async_block_till_done()
        await poll_clock.wait_for_sleep()

    (failsafe_task,) = [
        task for task in created if task.get_coro().__name__ == "set_failsafe"
    ]
    with pytest.raises(ValueError, match="Failsafe timeout must be between"):
        await failsafe_task
    assert station.commands == []
    assert "Could not set failsafe mode" not in caplog.text

    await stop_polling(hass)


async def test_setup_silent_station_currently_raises(
    hass: HomeAssistant,
    station: FakeKebaStation,
    poll_clock: PollClock,
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
    assert poll_clock.delays == []


async def test_setup_without_serial(
    hass: HomeAssistant,
    station: FakeKebaStation,
    poll_clock: PollClock,
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
    assert poll_clock.delays == []
    assert not hass.services.has_service(DOMAIN, "request_data")


async def test_polls_every_refresh_interval(
    hass: HomeAssistant, setup_keba: FakeKebaStation, poll_clock: PollClock
) -> None:
    """Test the polling loop requests every report, then waits 5 seconds."""
    station = setup_keba
    sent_before = len(station.sent)

    await poll_clock.tick()

    assert station.sent[sent_before:] == REPORTS
    assert poll_clock.delays == [5, 5]


@pytest.mark.parametrize(
    ("refresh_interval", "expected_delay"),
    [(2, 5), (5, 5), (30, 30)],
)
async def test_refresh_interval_has_a_floor(
    hass: HomeAssistant,
    station: FakeKebaStation,
    poll_clock: PollClock,
    refresh_interval: int,
    expected_delay: int,
) -> None:
    """Test the polling interval is the configured one, but never under 5 seconds."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"host": HOST, "refresh_interval": refresh_interval}}
    )
    await hass.async_block_till_done()
    await poll_clock.wait_for_sleep()

    assert poll_clock.delays == [expected_delay]

    await stop_polling(hass)


async def test_command_switches_to_fast_polling(
    hass: HomeAssistant, setup_keba: FakeKebaStation, poll_clock: PollClock
) -> None:
    """Test a command triggers four polls 2 seconds apart, then the normal interval."""
    station = setup_keba

    await hass.services.async_call(DOMAIN, "enable", blocking=True)
    await poll_clock.wait_for_sleep()
    for _ in range(4):
        await poll_clock.tick()

    assert station.commands[-1] == "ena 1"
    assert poll_clock.delays == [5, 2, 2, 2, 2, 5]
