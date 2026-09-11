"""Fixtures for the Swisscom Internet-Box integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.swisscom.const import DOMAIN

from .const import TEST_BASE_MAC, TEST_FORMATTED_MAC, TEST_MODEL_NAME, USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=TEST_MODEL_NAME,
        domain=DOMAIN,
        data=USER_INPUT,
        unique_id=TEST_FORMATTED_MAC,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.swisscom.async_setup_entry", return_value=True
    ) as mock_fn:
        yield mock_fn


@pytest.fixture
def mock_swisscom_client() -> Generator[MagicMock]:
    """Mock the SwisscomClient used in the config flow."""
    box_info = MagicMock()
    box_info.base_mac = TEST_BASE_MAC
    box_info.model_name = TEST_MODEL_NAME

    with patch(
        "homeassistant.components.swisscom.config_flow.SwisscomClient",
        autospec=True,
    ) as mock_cls:
        client = mock_cls.return_value
        client.login = AsyncMock()
        client.get_box_info = AsyncMock(return_value=box_info)
        yield client
