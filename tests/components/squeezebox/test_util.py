"""Test squeezebox util functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.squeezebox.util import safe_library_call
from homeassistant.exceptions import HomeAssistantError


async def test_safe_library_call_success() -> None:
    """Test successful sync and async calls."""
    # Test sync
    sync_method = MagicMock(return_value="success")
    assert await safe_library_call(sync_method, translation_key="test") == "success"

    # Test async
    async_method = AsyncMock(return_value="async_success")
    assert (
        await safe_library_call(async_method, translation_key="test") == "async_success"
    )


async def test_safe_library_call_raises_error() -> None:
    """Test that False or None return values raise HomeAssistantError."""
    fail_method = MagicMock(return_value=False)

    with pytest.raises(HomeAssistantError) as exc:
        await safe_library_call(fail_method, translation_key="error_key")

    assert exc.value.translation_key == "error_key"


async def test_safe_library_call_value_error() -> None:
    """Test that ValueError is caught and wraps into HomeAssistantError."""
    error_method = MagicMock(side_effect=ValueError)

    with pytest.raises(HomeAssistantError):
        await safe_library_call(error_method, translation_key="value_error_key")
