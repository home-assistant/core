"""Common fixtures for the Volvo On Call tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.volvooncall.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.volvooncall.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Volvo On Call will be removed ❌",
        data={},
    )
