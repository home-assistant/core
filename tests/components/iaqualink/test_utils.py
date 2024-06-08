"""Tests for iAqualink integration utility functions."""

from iaqualink.exception import AqualinkServiceException
import pytest

from homeassistant.components.iaqualink.utils import await_or_reraise
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import async_raises, async_returns


async def test_await_or_reraise(hass: HomeAssistant) -> None:
    """Test await_or_reraise for all values of awaitable."""
    async_noop = async_returns(None)
    await await_or_reraise(async_noop())

    with pytest.raises(Exception) as exc_info:
        async_ex = async_raises(Exception("Test exception"))
        await await_or_reraise(async_ex())
    assert str(exc_info.value) == "Test exception"

    with pytest.raises(HomeAssistantError):
        async_ex = async_raises(AqualinkServiceException)
        await await_or_reraise(async_ex())
