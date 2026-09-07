"""Tests for SNMP sensor platform setup behaviour."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from pysnmp.proto.rfc1902 import Integer32

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.snmp.sensor import (
    FAILURES_BEFORE_BACKOFF,
    MIN_BACKOFF,
    SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed

CONFIG = {
    SENSOR_DOMAIN: {
        "platform": "snmp",
        "host": "192.168.1.32",
        "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
    },
}


async def test_setup_fetches_once(hass: HomeAssistant) -> None:
    """Test setup performs only one SNMP fetch."""
    get_cmd = AsyncMock(return_value=(None, None, None, [[Integer32(13)]]))

    with patch("homeassistant.components.snmp.sensor.get_cmd", get_cmd):
        assert await async_setup_component(hass, SENSOR_DOMAIN, CONFIG)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.snmp").state == "13"
    assert get_cmd.call_count == 1


async def test_entity_recovers_when_device_unreachable(hass: HomeAssistant) -> None:
    """Test an entity unreachable at setup recovers on the next poll."""
    get_cmd = AsyncMock(
        side_effect=[
            ("No SNMP response received before timeout", None, None, None),
            (None, None, None, [[Integer32(13)]]),
        ]
    )

    with patch("homeassistant.components.snmp.sensor.get_cmd", get_cmd):
        assert await async_setup_component(hass, SENSOR_DOMAIN, CONFIG)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.snmp")
        assert state is not None
        assert state.state == "unknown"

        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.snmp").state == "13"


TIMEOUT_RESULT = ("No SNMP response received before timeout", None, None, None)
OK_RESULT = (None, None, None, [[Integer32(13)]])


async def test_backoff_when_device_stays_unreachable(hass: HomeAssistant) -> None:
    """Test polling backs off, recovers and resets for an unreachable device."""
    get_cmd = AsyncMock(return_value=TIMEOUT_RESULT)
    clock = 0.0
    now = dt_util.utcnow()
    interval = SCAN_INTERVAL.total_seconds()
    skipped_polls = int(MIN_BACKOFF // interval)

    def _monotonic() -> float:
        return clock

    async def _poll() -> None:
        """Advance the scan timer and the backoff clock by one interval."""
        nonlocal clock, now
        clock += interval
        now += SCAN_INTERVAL
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()

    with (
        patch("homeassistant.components.snmp.sensor.get_cmd", get_cmd),
        patch("homeassistant.components.snmp.sensor.monotonic", _monotonic),
    ):
        assert await async_setup_component(hass, SENSOR_DOMAIN, CONFIG)
        await hass.async_block_till_done()
        assert get_cmd.call_count == 1

        # Early failures are still retried on every scan interval.
        for expected in range(2, FAILURES_BEFORE_BACKOFF + 1):
            await _poll()
            assert get_cmd.call_count == expected

        # Threshold passed: the next MIN_BACKOFF seconds of polls are skipped.
        calls = get_cmd.call_count
        for _ in range(skipped_polls):
            await _poll()
        assert get_cmd.call_count == calls

        # Once the delay expires, polling resumes.
        await _poll()
        assert get_cmd.call_count == calls + 1

        # That failure doubled the delay, so MIN_BACKOFF is no longer enough.
        calls = get_cmd.call_count
        for _ in range(skipped_polls):
            await _poll()
        assert get_cmd.call_count == calls

        # A success clears the backoff entirely.
        clock += 2 * MIN_BACKOFF
        now += timedelta(seconds=2 * MIN_BACKOFF)
        get_cmd.return_value = OK_RESULT
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.snmp").state == "13"

        # Normal polling resumes immediately after recovery.
        calls = get_cmd.call_count
        await _poll()
        assert get_cmd.call_count == calls + 1
