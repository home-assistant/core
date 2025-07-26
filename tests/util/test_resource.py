"""Test the resource utility module."""

import os
import resource
from unittest.mock import patch

import pytest

from homeassistant.util.resource import (
    DEFAULT_SOFT_FILE_LIMIT,
    set_open_file_descriptor_limit,
)


@pytest.mark.parametrize(
    ("original_soft", "should_increase"),
    [
        (1024, True),
        (DEFAULT_SOFT_FILE_LIMIT - 1, True),
        (DEFAULT_SOFT_FILE_LIMIT, False),
        (DEFAULT_SOFT_FILE_LIMIT + 1, False),
    ],
)
def test_set_open_file_descriptor_limit_default(
    caplog: pytest.LogCaptureFixture, original_soft: int, should_increase: bool
) -> None:
    """Test setting file limit with default value."""
    original_hard = 524288
    with (
        patch(
            "homeassistant.util.resource.resource.getrlimit",
            return_value=(original_soft, original_hard),
        ),
        patch("homeassistant.util.resource.resource.setrlimit") as mock_setrlimit,
    ):
        set_open_file_descriptor_limit()

    if should_increase:
        mock_setrlimit.assert_called_once_with(
            resource.RLIMIT_NOFILE, (DEFAULT_SOFT_FILE_LIMIT, original_hard)
        )
    else:
        mock_setrlimit.assert_not_called()
        assert f"Current soft limit ({original_soft}) is already" in caplog.text


@pytest.mark.parametrize(
    ("original_soft", "custom_limit", "should_increase"),
    [
        (1499, 1500, True),
        (1500, 1500, False),
        (1501, 1500, False),
    ],
)
def test_set_open_file_descriptor_limit_environment_variable(
    caplog: pytest.LogCaptureFixture,
    original_soft: int,
    custom_limit: int,
    should_increase: bool,
) -> None:
    """Test setting file limit from environment variable."""
    original_hard = 524288
    with (
        patch.dict(os.environ, {"SOFT_FILE_LIMIT": str(custom_limit)}),
        patch(
            "homeassistant.util.resource.resource.getrlimit",
            return_value=(original_soft, original_hard),
        ),
        patch("homeassistant.util.resource.resource.setrlimit") as mock_setrlimit,
    ):
        set_open_file_descriptor_limit()

    if should_increase:
        mock_setrlimit.assert_called_once_with(
            resource.RLIMIT_NOFILE, (custom_limit, original_hard)
        )
    else:
        mock_setrlimit.assert_not_called()
        assert f"Current soft limit ({original_soft}) is already" in caplog.text


def test_set_open_file_descriptor_limit_exceeds_hard_limit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setting file limit that exceeds hard limit."""
    original_soft, original_hard = (1024, 524288)
    excessive_limit = original_hard + 1

    with (
        patch.dict(os.environ, {"SOFT_FILE_LIMIT": str(excessive_limit)}),
        patch(
            "homeassistant.util.resource.resource.getrlimit",
            return_value=(original_soft, original_hard),
        ),
        patch("homeassistant.util.resource.resource.setrlimit") as mock_setrlimit,
    ):
        set_open_file_descriptor_limit()

    mock_setrlimit.assert_called_once_with(
        resource.RLIMIT_NOFILE, (original_hard, original_hard)
    )
    assert (
        f"Requested soft limit ({excessive_limit}) exceeds hard limit ({original_hard})"
        in caplog.text
    )


def test_set_open_file_descriptor_limit_os_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling OSError when setting file limit."""
    with (
        patch(
            "homeassistant.util.resource.resource.getrlimit",
            return_value=(1024, 524288),
        ),
        patch(
            "homeassistant.util.resource.resource.setrlimit",
            side_effect=OSError("Permission denied"),
        ),
    ):
        set_open_file_descriptor_limit()

    assert "Failed to set file descriptor limit" in caplog.text
    assert "Permission denied" in caplog.text


def test_set_open_file_descriptor_limit_value_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling ValueError when setting file limit."""
    with (
        patch.dict(os.environ, {"SOFT_FILE_LIMIT": "invalid_value"}),
        patch(
            "homeassistant.util.resource.resource.getrlimit",
            return_value=(1024, 524288),
        ),
    ):
        set_open_file_descriptor_limit()

    assert "Invalid file descriptor limit value" in caplog.text
    assert "'invalid_value'" in caplog.text
