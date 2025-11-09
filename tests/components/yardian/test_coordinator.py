"""Tests for the Yardian update coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pyyardian import NetworkException, NotAuthorizedException

from homeassistant.components.yardian.coordinator import YardianUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def _create_coordinator(hass: HomeAssistant) -> YardianUpdateCoordinator:
    entry = MockConfigEntry(
        domain="yardian",
        unique_id="yid123",
        data={
            "host": "1.2.3.4",
            "access_token": "token",
            "yid": "yid123",
            "model": "PRO1902",
        },
        title="Yardian Smart Sprinkler",
    )
    entry.add_to_hass(hass)
    controller = AsyncMock()
    controller.fetch_oper_info = AsyncMock()
    return YardianUpdateCoordinator(hass, entry, controller)


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (TimeoutError(), UpdateFailed),
        (NetworkException("down"), UpdateFailed),
        (Exception("boom"), UpdateFailed),
    ],
)
async def test_async_update_data_wraps_known_failures(
    hass: HomeAssistant,
    exception: Exception,
    expected: type[BaseException],
) -> None:
    """Ensure coordinator raises the expected HA errors."""

    coordinator = await _create_coordinator(hass)
    coordinator.controller.fetch_device_state.side_effect = exception

    with pytest.raises(expected):
        await coordinator._async_update_data()


async def test_async_update_data_handles_auth_error(hass: HomeAssistant) -> None:
    """NotAuthorizedException should raise ConfigEntryError."""

    coordinator = await _create_coordinator(hass)
    coordinator.controller.fetch_device_state.side_effect = NotAuthorizedException(
        "bad"
    )

    with pytest.raises(ConfigEntryError):
        await coordinator._async_update_data()
