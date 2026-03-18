"""Resource management utilities for Home Assistant."""

from __future__ import annotations

import logging
import os
import resource
from typing import Final

_LOGGER = logging.getLogger(__name__)

# Default soft file descriptor limit to set
DEFAULT_SOFT_FILE_LIMIT: Final = 2048


def set_open_file_descriptor_limit() -> None:
    """Set the maximum open file descriptor soft limit."""
    try:
        # Check environment variable first, then use default
        soft_limit = int(os.environ.get("SOFT_FILE_LIMIT", DEFAULT_SOFT_FILE_LIMIT))

        # Get current limits
        current_soft, current_hard = resource.getrlimit(resource.RLIMIT_NOFILE)

        _LOGGER.debug(
            "Current file descriptor limits: soft=%d, hard=%d",
            current_soft,
            current_hard,
        )

        # Don't increase if already at or above the desired limit
        if current_soft >= soft_limit:
            _LOGGER.debug(
                "Current soft limit (%d) is already >= desired limit (%d), skipping",
                current_soft,
                soft_limit,
            )
            return

        # Don't set soft limit higher than hard limit
        if soft_limit > current_hard:
            _LOGGER.warning(
                "Requested soft limit (%d) exceeds hard limit (%d), "
                "setting to hard limit",
                soft_limit,
                current_hard,
            )
            soft_limit = current_hard

        # Set the new soft limit
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft_limit, current_hard))

        # Verify the change
        new_soft, new_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        _LOGGER.info(
            "File descriptor limits updated: soft=%d->%d, hard=%d",
            current_soft,
            new_soft,
            new_hard,
        )

    except OSError as err:
        _LOGGER.error("Failed to set file descriptor limit: %s", err)
    except ValueError as err:
        _LOGGER.error("Invalid file descriptor limit value: %s", err)
