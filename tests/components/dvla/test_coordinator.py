"""Tests for the DVLA data update coordinator."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError
import pytest

from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.components.dvla.coordinator import DVLACoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


class MockResponse:
    """Mock aiohttp response."""

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        *,
        error: Exception | None = None,
        status: int = 200,
    ) -> None:
        """Initialize the mock response."""
        self._data = data or {}
        self._error = error
        self.status = status

    def raise_for_status(self) -> None:
        """Raise a mocked HTTP error."""
        if self._error is not None:
            raise self._error

    async def json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        """Return mocked JSON data."""
        return self._data


def create_coordinator(
    hass: HomeAssistant,
    session: MagicMock,
    reg_number: str = "AB12CDE",
) -> DVLACoordinator:
    """Create a DVLA coordinator."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=reg_number,
        data={
            CONF_REG_NUMBER: reg_number,
        },
    )
    entry.add_to_hass(hass)

    return DVLACoordinator(
        hass,
        entry,
        session,
        reg_number,
    )


async def test_async_update_data_returns_vehicle_data(hass: HomeAssistant) -> None:
    """Test coordinator returns vehicle data from the DVLA API."""
    vehicle_data = {
        "registrationNumber": "AB12CDE",
        "make": "FORD",
        "taxStatus": "Taxed",
    }
    session = MagicMock()
    session.post = AsyncMock(return_value=MockResponse(vehicle_data))

    coordinator = create_coordinator(hass, session)

    result = await coordinator._async_update_data()

    assert result == vehicle_data

    session.post.assert_called_once()
    assert session.post.call_args.kwargs["json"] == {
        "registrationNumber": "AB12CDE",
    }
    assert "x-api-key" in session.post.call_args.kwargs["headers"]


async def test_async_update_data_normalizes_registration_number(
    hass: HomeAssistant,
) -> None:
    """Test coordinator strips spaces and uppercases the registration number."""
    session = MagicMock()
    session.post = AsyncMock(
        return_value=MockResponse(
            {
                "registrationNumber": "AB12CDE",
                "make": "FORD",
            }
        )
    )
    coordinator = create_coordinator(hass, session, "ab12 cde")

    await coordinator._async_update_data()

    assert session.post.call_args.kwargs["json"] == {
        "registrationNumber": "AB12CDE",
    }


async def test_async_update_data_raises_update_failed_on_client_error(
    hass: HomeAssistant,
) -> None:
    """Test coordinator raises UpdateFailed on client errors."""
    session = MagicMock()
    session.post = AsyncMock(side_effect=ClientError("API error"))

    coordinator = create_coordinator(hass, session)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_async_update_data_raises_update_failed_on_unauthorized(
    hass: HomeAssistant,
) -> None:
    """Test coordinator raises UpdateFailed on auth errors."""
    session = MagicMock()
    session.post = AsyncMock(
        return_value=MockResponse(
            {"message": "Invalid authentication credentials"},
            status=401,
        )
    )

    coordinator = create_coordinator(hass, session)

    with pytest.raises(UpdateFailed, match="Invalid authentication credentials"):
        await coordinator._async_update_data()


async def test_async_update_data_raises_update_failed_on_rate_limit(
    hass: HomeAssistant,
) -> None:
    """Test coordinator raises UpdateFailed on rate limit errors."""
    session = MagicMock()
    session.post = AsyncMock(
        return_value=MockResponse(
            {"message": "API rate limit exceeded."},
            status=429,
        )
    )

    coordinator = create_coordinator(hass, session)

    with pytest.raises(UpdateFailed, match="rate limit"):
        await coordinator._async_update_data()


async def test_async_update_data_raises_update_failed_on_api_errors(
    hass: HomeAssistant,
) -> None:
    """Test coordinator raises UpdateFailed on DVLA API errors."""
    session = MagicMock()
    session.post = AsyncMock(
        return_value=MockResponse(
            {
                "errors": [
                    {
                        "title": "Bad Request",
                        "code": "400",
                        "detail": "Invalid registration number",
                    }
                ]
            },
            status=400,
        )
    )

    coordinator = create_coordinator(hass, session)

    with pytest.raises(UpdateFailed, match="Invalid registration number"):
        await coordinator._async_update_data()


async def test_async_update_data_raises_update_failed_on_invalid_json(
    hass: HomeAssistant,
) -> None:
    """Test coordinator raises UpdateFailed on invalid JSON."""
    session = MagicMock()
    response = MockResponse()
    response.json = AsyncMock(side_effect=ValueError("invalid json"))
    session.post = AsyncMock(return_value=response)

    coordinator = create_coordinator(hass, session)

    with pytest.raises(UpdateFailed, match="Invalid response"):
        await coordinator._async_update_data()


async def test_async_update_data_raises_update_failed_on_timeout(
    hass: HomeAssistant,
) -> None:
    """Test coordinator raises UpdateFailed on request timeout."""
    session = MagicMock()
    session.post = AsyncMock(side_effect=TimeoutError)

    coordinator = create_coordinator(hass, session)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_async_update_data_raises_update_failed_on_message(
    hass: HomeAssistant,
) -> None:
    """Test coordinator raises UpdateFailed on message response."""
    session = MagicMock()
    session.post = AsyncMock(
        return_value=MockResponse(
            {"message": "Vehicle not found"},
            status=400,
        )
    )

    coordinator = create_coordinator(hass, session)

    with pytest.raises(UpdateFailed, match="Vehicle not found"):
        await coordinator._async_update_data()


async def test_async_update_data_raises_update_failed_on_http_error_without_message(
    hass: HomeAssistant,
) -> None:
    """Test coordinator raises UpdateFailed on HTTP error without message."""
    session = MagicMock()
    session.post = AsyncMock(
        return_value=MockResponse(
            {"unexpected": "response"},
            status=500,
        )
    )

    coordinator = create_coordinator(hass, session)

    with pytest.raises(UpdateFailed, match="status 500"):
        await coordinator._async_update_data()


async def test_async_update_data_raises_update_failed_on_auth_message(
    hass: HomeAssistant,
) -> None:
    """Test coordinator raises UpdateFailed on auth message response."""
    session = MagicMock()
    session.post = AsyncMock(
        return_value=MockResponse(
            {"message": "Invalid authentication credentials"},
            status=200,
        )
    )

    coordinator = create_coordinator(hass, session)

    with pytest.raises(UpdateFailed, match="Invalid authentication credentials"):
        await coordinator._async_update_data()


async def test_async_update_data_raises_update_failed_on_rate_limit_message(
    hass: HomeAssistant,
) -> None:
    """Test coordinator raises UpdateFailed on rate limit message response."""
    session = MagicMock()
    session.post = AsyncMock(
        return_value=MockResponse(
            {"message": "API rate limit exceeded."},
            status=200,
        )
    )

    coordinator = create_coordinator(hass, session)

    with pytest.raises(UpdateFailed, match="API rate limit exceeded"):
        await coordinator._async_update_data()
