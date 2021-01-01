"""Define fixtures available for all tests."""
from unittest.mock import AsyncMock, patch

from pytest import fixture
from surepy import SurePetcare

from homeassistant.helpers.aiohttp_client import async_get_clientsession


@fixture
async def surepetcare(hass):
    """Mock the SurePetcare for easier testing."""
    with patch("homeassistant.components.surepetcare.SurePetcare") as mock_surepetcare:
        instance = mock_surepetcare.return_value = SurePetcare(
            "test-username",
            "test-password",
            hass.loop,
            async_get_clientsession(hass),
            api_timeout=1,
        )
        instance.get_data = AsyncMock(return_value=None)

        yield mock_surepetcare
