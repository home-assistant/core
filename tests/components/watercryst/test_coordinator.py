"""Tests for WATERCryst update coordinators."""

from asyncio import CancelledError
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.watercryst.coordinator import (
    MeasurementsUpdateCoordinator,
    StateUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_measurements_update_success(hass: HomeAssistant) -> None:
    """Test a successful measurements update."""
    measurements = object()
    client = MagicMock()
    client.get_measurements = AsyncMock(return_value=measurements)

    coordinator = MeasurementsUpdateCoordinator(
        hass=hass,
        entry=MagicMock(),
        client=client,
    )

    assert coordinator.name == "Measurements update coordinator"
    assert coordinator.update_interval == timedelta(seconds=60)
    assert await coordinator._async_update_data() is measurements
    client.get_measurements.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("language", "expected_locale"),
    [("de-AT", "de"), ("fr-FR", "en")],
)
async def test_state_update_success(
    hass: HomeAssistant,
    language: str,
    expected_locale: str,
) -> None:
    """Test state updates use supported locales and fall back to English."""
    hass.config.language = language
    state = object()
    client = MagicMock()
    client.get_state = AsyncMock(return_value=state)

    coordinator = StateUpdateCoordinator(
        hass=hass,
        entry=MagicMock(),
        client=client,
    )

    assert coordinator.name == "State update coordinator"
    assert coordinator.update_interval == timedelta(seconds=30)
    assert await coordinator._async_update_data() is state
    client.get_state.assert_awaited_once_with(locale=expected_locale)


@pytest.mark.parametrize(
    ("coordinator_class", "client_method", "message"),
    [
        (
            MeasurementsUpdateCoordinator,
            "get_measurements",
            "Failed to update measurements",
        ),
        (StateUpdateCoordinator, "get_state", "Failed to update state"),
    ],
)
async def test_update_error(
    hass: HomeAssistant,
    coordinator_class: type[MeasurementsUpdateCoordinator | StateUpdateCoordinator],
    client_method: str,
    message: str,
) -> None:
    """Test coordinator exceptions become update failures."""
    error = RuntimeError("API unavailable")
    client = MagicMock()
    setattr(client, client_method, AsyncMock(side_effect=error))
    coordinator = coordinator_class(
        hass=hass,
        entry=MagicMock(),
        client=client,
    )

    with pytest.raises(UpdateFailed, match=message) as exc_info:
        await coordinator._async_update_data()

    assert exc_info.value.__cause__ is error


@pytest.mark.parametrize(
    ("coordinator_class", "client_method"),
    [
        (MeasurementsUpdateCoordinator, "get_measurements"),
        (StateUpdateCoordinator, "get_state"),
    ],
)
async def test_update_cancelled(
    hass: HomeAssistant,
    coordinator_class: type[MeasurementsUpdateCoordinator | StateUpdateCoordinator],
    client_method: str,
) -> None:
    """Test task cancellation is propagated unchanged."""
    client = MagicMock()
    setattr(client, client_method, AsyncMock(side_effect=CancelledError))
    coordinator = coordinator_class(
        hass=hass,
        entry=MagicMock(),
        client=client,
    )

    with pytest.raises(CancelledError):
        await coordinator._async_update_data()
