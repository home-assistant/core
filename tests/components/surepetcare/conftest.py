"""Define fixtures available for all tests."""
from unittest.mock import AsyncMock, patch

from pytest import fixture
from surepy import Surepy

from homeassistant.helpers.aiohttp_client import async_get_clientsession


@fixture
async def surepetcare(hass):
    """Mock the SurePetcare for easier testing."""
    with patch("homeassistant.components.surepetcare.Surepy") as mock_surepetcare:
        instance = mock_surepetcare.return_value = Surepy(
            "test-username",
            "test-password",
            session=async_get_clientsession(hass),
            api_timeout=1,
        )
        instance.get_entities = AsyncMock(return_value=None)
        yield mock_surepetcare
