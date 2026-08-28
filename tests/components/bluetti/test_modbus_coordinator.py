"""Tests for BluettiModbusCoordinator."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from modbus_connection.exceptions import AcknowledgeError, ModbusConnectionError
import pytest

from homeassistant.components.bluetti.coordinator import BluettiModbusCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


def _device(values=None):
    device = MagicMock()
    device.async_update = AsyncMock()
    device.values = values or {}
    device.get_field.side_effect = lambda name: MagicMock(unit="W")
    return device


async def test_async_update_data_maps_results_by_name(hass: HomeAssistant) -> None:
    """Values read over Modbus are returned keyed by their field name."""
    device = _device(values={"b_soc": 42, "b_cycle_count": 12})
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", device)

    result = await coordinator._async_update_data()

    assert result["b_soc"].name == "b_soc"
    assert result["b_soc"].value == 42
    assert result["b_cycle_count"].value == 12


async def test_async_update_data_with_no_fields_returns_empty_dict(
    hass: HomeAssistant,
) -> None:
    """A device that reported no fields yields an empty result, not an error."""
    device = _device()
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", device)

    result = await coordinator._async_update_data()

    assert result == {}


async def test_modbus_error_becomes_update_failed(hass: HomeAssistant) -> None:
    """A Modbus error is surfaced as UpdateFailed, not the raw exception."""
    device = _device()
    device.async_update = AsyncMock(
        side_effect=ModbusConnectionError("no route to host")
    )
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", device)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_retries_once_after_an_acknowledge_response(hass: HomeAssistant) -> None:
    """An AcknowledgeError is retried once and can still succeed."""
    device = _device(values={"b_soc": 42})
    device.async_update = AsyncMock(side_effect=[AcknowledgeError(5), None])
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", device)

    result = await coordinator._async_update_data()

    assert device.async_update.await_count == 2
    assert result["b_soc"].value == 42


async def test_gives_up_after_a_second_acknowledge_response(
    hass: HomeAssistant,
) -> None:
    """A second consecutive AcknowledgeError is not retried again."""
    device = _device()
    device.async_update = AsyncMock(
        side_effect=[AcknowledgeError(5), AcknowledgeError(5)]
    )
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", device)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert device.async_update.await_count == 2


async def test_survives_a_slow_update_within_the_overall_budget(
    hass: HomeAssistant,
) -> None:
    """A single slow register block must not exhaust the whole update's timeout.

    Regression test for the same "Request cancelled outside library" bug
    fixed in bluetti-modbus PR #26: the per-update timeout budgets the whole
    sequential multi-block read, not one request, so it must comfortably
    survive one block being slow. Shrinks UPDATE_TIMEOUT rather than
    sleeping through a real 30s budget - the ratio (a slow update taking
    ~60% of the budget) is what's under test, not the literal duration.
    """
    device = _device(values={"b_soc": 42})

    async def slow_update() -> None:
        await asyncio.sleep(0.06)

    device.async_update = AsyncMock(side_effect=slow_update)
    coordinator = BluettiModbusCoordinator(hass, MagicMock(), "SN1", device)

    with patch(
        "homeassistant.components.bluetti.coordinator.UPDATE_TIMEOUT",
        timedelta(seconds=0.1),
    ):
        result = await coordinator._async_update_data()

    assert result["b_soc"].value == 42
