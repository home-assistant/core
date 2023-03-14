"""Test fixtures for imap email content sensor component."""
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_client() -> Generator[MagicMock, None, None]:
    """Mock the imap client."""
    with patch(
        "homeassistant.components.imap_email_content.sensor.EmailReader.read_next",
        return_value=None,
    ), patch("imaplib.IMAP4_SSL") as mock_imap_client:
        yield mock_imap_client
