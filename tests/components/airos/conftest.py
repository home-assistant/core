"""Common fixtures for the Ubiquiti airOS tests."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

import pytest

from tests.common import load_fixture


@pytest.fixture
def ap_fixture():
    """Load fixture data for AP mode."""
    return json.loads(load_fixture("airos/ap-ptp.json"))


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.airos.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
