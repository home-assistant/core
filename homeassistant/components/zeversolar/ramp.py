"""Async power limit ramp controller for Zeversolar."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    HTTP_TIMEOUT,
    MINIMUM_LIMIT,
    STEP_INTERVAL_DOWN,
    STEP_INTERVAL_UP,
    STEP_SIZE,
)

_LOGGER = logging.getLogger(__name__)

ProgressCallback = Callable[[int], Awaitable[None]]


def _clamp(value: int) -> int:
    return max(MINIMUM_LIMIT, min(100, value))


async def _async_write_limit(hass: HomeAssistant, host: str, limit: int) -> None:
    """POST a power limit to the inverter.

    The inverter closes the TCP connection after processing the POST without
    sending an HTTP response — ServerDisconnectedError is treated as success.
    """
    session = async_get_clientsession(hass)
    # Fields reverse-engineered from the inverter's own web interface (pwrlim.cgi).
    # These replicate exactly what the browser sends when saving power limit settings.
    data = {
        "enlim": "on",  # enable power limiting
        "ac_sys": "0",  # AC system type: 0 = single phase
        "ac_mode": "1",  # limit mode: 1 = percentage-based
        "ac_value1": str(limit),  # active power limit (5–100%)
        "ac_value2": "0",  # reactive power limit (unused in mode 1)
        "em_ml": "0",  # export management minimum limit
        "ac_value3": "60",  # frequency reference (Hz)
        "drm_sp": "16.67",  # DRM setpoint (Demand Response Mode, grid compliance default)
    }
    try:
        async with session.post(
            f"http://{host}/pwrlim.cgi",
            data=data,
            timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
        ) as resp:
            await resp.read()
    except aiohttp.ServerDisconnectedError:
        # Normal — inverter closes connection after processing without responding.
        pass


async def async_ramp(
    hass: HomeAssistant,
    host: str,
    target: int,
    on_step: ProgressCallback | None = None,
) -> None:
    """Ramp power limit toward target in STEP_SIZE increments.

    Calls on_step(value) after each successful write so the UI can update
    in real time while the ramp is in progress.

    Args:
        hass:    HomeAssistant instance.
        host:    Inverter IP address.
        target:  Target power limit percentage (will be clamped to MINIMUM_LIMIT–100).
        on_step: Optional async callback called after each step with the new value.

    """
    target = _clamp(target)

    # Read current state from the inverter — do not trust HA entity state.
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"http://{host}/adv.cgi",
            timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
        ) as resp:
            text = await resp.text()
            lines = text.splitlines()
    except Exception as err:  # noqa: BLE001
        _LOGGER.error("Ramp aborted — cannot read current limit: %s", err)
        return

    if len(lines) < 12:
        _LOGGER.error(
            "Ramp aborted — adv.cgi returned %d lines, expected ≥12", len(lines)
        )
        return

    try:
        current = int(float(lines[11].strip()))
    except ValueError as err:
        _LOGGER.error("Ramp aborted — cannot parse current limit: %s", err)
        return

    if current == target:
        return

    ramping_down = target < current
    direction = -STEP_SIZE if ramping_down else STEP_SIZE
    interval = STEP_INTERVAL_DOWN if ramping_down else STEP_INTERVAL_UP

    _LOGGER.debug("Ramping power limit: %d%% → %d%%", current, target)

    next_val = current
    while next_val != target:
        next_val = _clamp(next_val + direction)
        # Don't overshoot
        if (direction < 0 and next_val < target) or (
            direction > 0 and next_val > target
        ):
            next_val = target

        try:
            await _async_write_limit(hass, host, next_val)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Ramp aborted at %d%% — write failed: %s (inverter left at last successful value)",
                next_val,
                err,
            )
            return

        _LOGGER.debug("Power limit set to %d%%", next_val)

        if on_step is not None:
            await on_step(next_val)

        if next_val != target:
            await asyncio.sleep(interval)

    _LOGGER.debug("Ramp complete — limit is now %d%%", target)
