"""Tests for the DVLA data update coordinator."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError
import pytest

from homeassistant.components.dvla.const import CONF_CALENDARS, CONF_REG_NUMBER, DOMAIN
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
            CONF_CALENDARS: ["None"],
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
