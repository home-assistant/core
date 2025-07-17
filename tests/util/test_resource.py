"""Test the resource utility module."""

import os
import resource
from unittest.mock import patch

from homeassistant.util.resource import (
    DEFAULT_SOFT_FILE_LIMIT,
    set_open_file_descriptor_limit,
)


def test_set_open_file_descriptor_limit_default() -> None:
    """Test setting file limit with default value."""
    original_soft, original_hard = resource.getrlimit(resource.RLIMIT_NOFILE)

    with patch("homeassistant.util.resource._LOGGER") as mock_logger:
        set_open_file_descriptor_limit()

        # Check that we attempted to set the limit
        new_soft, new_hard = resource.getrlimit(resource.RLIMIT_NOFILE)

        # If the original soft limit was already >= DEFAULT_SOFT_FILE_LIMIT,
        # it should remain unchanged
        if original_soft >= DEFAULT_SOFT_FILE_LIMIT:
            assert new_soft == original_soft
            mock_logger.debug.assert_called()
        else:
            # Should have been increased to DEFAULT_SOFT_FILE_LIMIT or hard limit
            expected_soft = min(DEFAULT_SOFT_FILE_LIMIT, original_hard)
            assert new_soft == expected_soft
            mock_logger.info.assert_called()


def test_set_open_file_descriptor_limit_environment_variable() -> None:
    """Test setting file limit from environment variable."""
    custom_limit = 1500

    with (
        patch.dict(os.environ, {"SOFT_FILE_LIMIT": str(custom_limit)}),
        patch("homeassistant.util.resource._LOGGER") as mock_logger,
    ):
        original_soft, original_hard = resource.getrlimit(resource.RLIMIT_NOFILE)

        set_open_file_descriptor_limit()

        new_soft, new_hard = resource.getrlimit(resource.RLIMIT_NOFILE)

        if original_soft >= custom_limit:
            assert new_soft == original_soft
            mock_logger.debug.assert_called()
        else:
            expected_soft = min(custom_limit, original_hard)
            assert new_soft == expected_soft


def test_set_open_file_descriptor_limit_exceeds_hard_limit() -> None:
    """Test setting file limit that exceeds hard limit."""
    original_soft, original_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    excessive_limit = original_hard + 1000

    with (
        patch.dict(os.environ, {"SOFT_FILE_LIMIT": str(excessive_limit)}),
        patch("homeassistant.util.resource._LOGGER") as mock_logger,
    ):
        set_open_file_descriptor_limit()

        new_soft, new_hard = resource.getrlimit(resource.RLIMIT_NOFILE)

        # Should be capped at hard limit
        assert new_soft == original_hard
        mock_logger.warning.assert_called_once()


def test_set_open_file_descriptor_limit_os_error() -> None:
    """Test handling OSError when setting file limit."""
    with (
        patch(
            "homeassistant.util.resource.resource.getrlimit", return_value=(1000, 4096)
        ),
        patch(
            "homeassistant.util.resource.resource.setrlimit",
            side_effect=OSError("Permission denied"),
        ),
        patch("homeassistant.util.resource._LOGGER") as mock_logger,
    ):
        set_open_file_descriptor_limit()

        mock_logger.error.assert_called_once()
        assert (
            "Failed to set file descriptor limit" in mock_logger.error.call_args[0][0]
        )
