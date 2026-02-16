"""Test Meraki Dashboard API client."""

from __future__ import annotations

from typing import Self
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.meraki_dashboard.api import (
    MerakiDashboardApi,
    MerakiDashboardApiRateLimitError,
)


class _MockResponse:
    """Minimal aiohttp response mock."""

    def __init__(
        self,
        status: int,
        payload: object | None = None,
        headers: dict[str, str] | None = None,
        content_length: int | None = 1,
    ) -> None:
        """Initialize mock response."""
        self.status = status
        self._payload = payload
        self.headers = headers or {}
        self.content_length = content_length

    async def __aenter__(self) -> Self:
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        """Exit async context."""
        return False

    async def json(self) -> object:
        """Return payload."""
        return self._payload


async def test_get_retries_on_rate_limit_then_succeeds() -> None:
    """Test GET retries when API returns 429."""
    session = AsyncMock()
    session.get = AsyncMock(
        side_effect=[
            _MockResponse(429, headers={"Retry-After": "1"}),
            _MockResponse(200, payload=[]),
        ]
    )
    api = MerakiDashboardApi(session, "api-key")

    with patch(
        "homeassistant.components.meraki_dashboard.api.asyncio.sleep",
        AsyncMock(),
    ) as mock_sleep:
        organizations = await api.async_get_organizations()

    assert organizations == []
    mock_sleep.assert_awaited_once_with(1.0)


async def test_get_raises_rate_limit_after_retries() -> None:
    """Test GET raises if API keeps returning 429."""
    session = AsyncMock()
    session.get = AsyncMock(
        side_effect=[_MockResponse(429, headers={"Retry-After": "2"}) for _ in range(5)]
    )
    api = MerakiDashboardApi(session, "api-key")

    with (
        patch(
            "homeassistant.components.meraki_dashboard.api.asyncio.sleep",
            AsyncMock(),
        ) as mock_sleep,
        pytest.raises(MerakiDashboardApiRateLimitError),
    ):
        await api.async_get_organizations()

    assert mock_sleep.await_count == 4
