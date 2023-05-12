"""Fixtrues for the Nextcloud integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.fixture
def mock_nextcloud_monitor() -> Mock:
    """Mock of NextcloudMonitor."""
    ncm = Mock(
        update=Mock(return_value=True),
    )

    return ncm


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nextcloud.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
