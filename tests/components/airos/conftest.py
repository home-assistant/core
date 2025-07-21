"""Common fixtures for the Ubiquiti airOS tests."""

from collections.abc import Generator
import json
from typing import Any
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


@pytest.fixture
def mock_airos_client(ap_fixture: dict[str, Any]):
    """Fixture to mock the AirOS API client."""
    with patch(
        "homeassistant.components.airos.AirOS", autospec=True
    ) as mock_airos_class:
        mock_client_instance = mock_airos_class.return_value
        mock_client_instance.login.return_value = True
        mock_client_instance.status.return_value = ap_fixture
        yield mock_airos_class
