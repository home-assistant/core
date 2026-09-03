"""Test VRChat integration utility helpers."""

import asyncio
import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.vrchat.utils import (
    EXCEPTION_MESSAGE_ASYNC_CLEANUP,
    AsyncCleanups,
    _async_run_cleanup,
    is_user_in_game,
    normalize_vrchat_enum_value,
    parse_vrchat_location_string,
    process_vrchat_string,
    svg_file_uri,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(None, None, id="none"),
        pytest.param("", None, id="empty"),
        pytest.param("value", "value", id="value"),
    ],
)
def test_process_vrchat_string(value: str | None, expected: str | None) -> None:
    """Test empty VRChat strings are treated as missing."""
    assert process_vrchat_string(value) == expected


def test_normalize_and_encode_vrchat_values() -> None:
    """Test enum normalization and SVG data URI encoding."""
    assert normalize_vrchat_enum_value("active on web") == "active_on_web"
    assert normalize_vrchat_enum_value("") is None
    assert svg_file_uri("<svg />").startswith(
        "data:image/svg+xml;charset=utf-8;base64,"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(None, (None, None), id="missing"),
        pytest.param("offline", ("offline", "offline"), id="special"),
        pytest.param(
            "wrld_test:instance", ("wrld_test", "instance"), id="world_instance"
        ),
        pytest.param("wrld_test", ("wrld_test", None), id="world"),
        pytest.param("instance", (None, "instance"), id="instance"),
    ],
)
def test_parse_vrchat_location_string(
    value: str | None, expected: tuple[str | None, str | None]
) -> None:
    """Test VRChat location parsing."""
    result = parse_vrchat_location_string(value)

    assert result == expected
    assert all(type(part) is str for part in result if part is not None)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param({}, None, id="missing"),
        pytest.param({"location": "offline"}, False, id="offline"),
        pytest.param({"world": "wrld_test"}, True, id="world"),
        pytest.param({"instance": "offline:offline"}, False, id="offline_instance"),
    ],
)
def test_is_user_in_game(data: dict[str, str], expected: bool | None) -> None:
    """Test whether a user is in a VRChat world."""
    assert is_user_in_game(data) is expected


async def test_async_run_cleanup_logs_errors(caplog: pytest.LogCaptureFixture) -> None:
    """Test cleanup timeout and exception handling."""

    async def failing_cleanup() -> None:
        raise RuntimeError("test error")

    async def stuck_cleanup() -> None:
        await asyncio.Event().wait()

    with caplog.at_level(logging.WARNING):
        await _async_run_cleanup(failing_cleanup())
    assert EXCEPTION_MESSAGE_ASYNC_CLEANUP in caplog.text

    with (
        patch("homeassistant.components.vrchat.utils.ASYNC_CLEANUP_TIMEOUT_SECOND", 0),
        caplog.at_level(logging.WARNING),
    ):
        await _async_run_cleanup(stuck_cleanup())
    assert "Timed out during async clean up" in caplog.text


async def test_async_cleanups_context_and_duplicate_close() -> None:
    """Test context manager cleanup and idempotent close."""
    cleanup = AsyncMock()
    manager = AsyncCleanups()
    manager.add_to_cleanups(cleanup)

    async with manager as returned:
        assert returned is manager

    await manager.close()
    cleanup.assert_awaited_once()
    assert manager.closed


async def test_async_cleanups_logs_sync_callback_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test synchronous cleanup callback errors do not stop closing."""
    manager = AsyncCleanups()
    callback = Mock(side_effect=RuntimeError("test error"))
    manager.add_to_cleanups(callback)

    with caplog.at_level(logging.ERROR):
        await manager.close()

    callback.assert_called_once_with()
    assert EXCEPTION_MESSAGE_ASYNC_CLEANUP in caplog.text
