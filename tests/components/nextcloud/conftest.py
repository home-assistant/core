"""Tests for the Nextcloud integration."""

from unittest.mock import Mock

import pytest


@pytest.fixture(name="mock_nextcloud_monitor")
def mock_nextcloud_monitor() -> Mock:
    """Mock of NextcloudMonitor."""
    ncm = Mock(
        update=Mock(return_value=True),
    )

    return ncm
