"""Test Visonic exception metadata, formatting and Home Assistant compatibility."""

import pytest

from homeassistant.components.visonic.exceptions import (
    VisonicAuthException,
    VisonicException,
)
from homeassistant.exceptions import HomeAssistantError


@pytest.mark.parametrize("exception_type", [VisonicException, VisonicAuthException])
@pytest.mark.parametrize(
    ("code", "prefix"),
    [
        (None, "Panel failed"),
        (0, "[Error 0] Panel failed"),
        (400, "[Error 400] Panel failed"),
    ],
)
@pytest.mark.parametrize(
    ("original", "suffix"),
    [
        pytest.param(None, "", id="no-cause"),
        pytest.param(
            ValueError("invalid panel response"),
            " (caused by ValueError('invalid panel response'))",
            id="with-cause",
        ),
    ],
)
def test_exception_metadata_and_formatting(
    exception_type: type[VisonicException],
    code: int | None,
    prefix: str,
    original: ValueError | None,
    suffix: str,
) -> None:
    """Preserve metadata and format optional codes and original exception details."""
    error = exception_type("Panel failed", code=code, original_exception=original)

    assert isinstance(error, VisonicException)
    assert isinstance(error, HomeAssistantError)
    assert error.args == ("Panel failed",)
    assert error.message == "Panel failed"
    assert error.code == code
    assert error.original_exception is original
    assert str(error) == prefix + suffix


@pytest.mark.parametrize("exception_type", [VisonicException, VisonicAuthException])
def test_message_only_defaults(exception_type: type[VisonicException]) -> None:
    """A message-only exception needs no code or underlying exception."""
    error = exception_type("Connection refused")
    assert error.code is None
    assert error.original_exception is None
    assert str(error) == "Connection refused"
    with pytest.raises(HomeAssistantError) as caught:
        raise error
    assert caught.value is error


def test_empty_message() -> None:
    """An empty message remains empty rather than acquiring an implicit error prefix."""
    error = VisonicException("")
    assert str(error) == ""
    assert error.args == ("",)
