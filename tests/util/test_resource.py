"""Test the resource utility module."""

import os
import resource
from unittest.mock import call, patch

import pytest

from homeassistant.util.resource import (
    DEFAULT_SOFT_FILE_LIMIT,
    set_open_file_descriptor_limit,
)


@pytest.mark.parametrize(
    ("original_soft", "expected_calls", "should_log_already_sufficient"),
    [
        (
            1024,
            [call(resource.RLIMIT_NOFILE, (DEFAULT_SOFT_FILE_LIMIT, 524288))],
            False,
        ),
        (
            DEFAULT_SOFT_FILE_LIMIT - 1,
            [call(resource.RLIMIT_NOFILE, (DEFAULT_SOFT_FILE_LIMIT, 524288))],
            False,
        ),
        (DEFAULT_SOFT_FILE_LIMIT, [], True),
        (DEFAULT_SOFT_FILE_LIMIT + 1, [], True),
    ],
)
def test_set_open_file_descriptor_limit_default(
    caplog: pytest.LogCaptureFixture,
    original_soft: int,
    expected_calls: list,
    should_log_already_sufficient: bool,
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

    assert mock_setrlimit.call_args_list == expected_calls
    assert (
        f"Current soft limit ({original_soft}) is already" in caplog.text
    ) is should_log_already_sufficient


@pytest.mark.parametrize(
    (
        "original_soft",
        "custom_limit",
        "expected_calls",
        "should_log_already_sufficient",
    ),
    [
        (1499, 1500, [call(resource.RLIMIT_NOFILE, (1500, 524288))], False),
        (1500, 1500, [], True),
        (1501, 1500, [], True),
    ],
)
def test_set_open_file_descriptor_limit_environment_variable(
    caplog: pytest.LogCaptureFixture,
    original_soft: int,
    custom_limit: int,
    expected_calls: list,
    should_log_already_sufficient: bool,
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

    assert mock_setrlimit.call_args_list == expected_calls
    assert (
        f"Current soft limit ({original_soft}) is already" in caplog.text
    ) is should_log_already_sufficient


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
