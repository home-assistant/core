"""Setup the QNAP tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

TEST_HOST = "1.2.3.4"
TEST_USERNAME = "admin"
TEST_PASSWORD = "password"
TEST_NAS_NAME = "Test NAS name"
TEST_SERIAL = "123456789"

TEST_SYSTEM_STATS = {"system": {"serial_number": TEST_SERIAL, "name": TEST_NAS_NAME}}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.qnap.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def qnap_connect(mock_get_source_ip: None) -> Generator[MagicMock, None, None]:
    """Mock qnap connection."""
    with patch(
        "homeassistant.components.qnap.config_flow.QNAPStats", autospec=True
    ) as host_mock_class:
        host_mock = host_mock_class.return_value
        host_mock.get_system_stats.return_value = TEST_SYSTEM_STATS
        yield host_mock
