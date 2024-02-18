"""Fixtrues for the Fyta integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.fixture
def mock_fyta_connector() -> Mock:
    """Mock of FytaConnector."""
    fyta = Mock(
        update=Mock(return_value=True),
    )
    return fyta


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fyta.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="validate_input")
def mock_controller():
    """Mock a successful _host_in_configuration_exists."""
    with patch(
        "homeassistant.components.solarlog.config_flow.validate_input",
        return_value={"username": "fyta_user", "password": "fyta_password"},
    ):
        yield
