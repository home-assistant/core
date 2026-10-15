"""Fixtures for Rituals Perfume Genie tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.rituals_perfume_genie.const import ACCOUNT_HASH, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import TEST_EMAIL, TEST_PASSWORD

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.rituals_perfume_genie.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_rituals_client() -> Generator[AsyncMock]:
    """Mock the Rituals Perfume Genie client."""
    with (
        patch(
            "homeassistant.components.rituals_perfume_genie.config_flow.RitualsGenie",
            autospec=True,
        ) as mock_client_cls,
        patch(
            "homeassistant.components.rituals_perfume_genie.RitualsGenie",
            new=mock_client_cls,
        ),
    ):
        yield mock_client_cls.return_value


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock Rituals Account."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_EMAIL,
        data={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
        title=TEST_EMAIL,
        version=2,
    )


@pytest.fixture
def old_mock_config_entry() -> MockConfigEntry:
    """Mock Rituals Account."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_EMAIL,
        data={ACCOUNT_HASH: "old_hash_should_be_removed"},
        title=TEST_EMAIL,
        version=1,
    )
