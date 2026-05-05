"""Common fixtures for the Data Grand Lyon tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.data_grandlyon.const import (
    CONF_LINE,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.data_grandlyon.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_subentries() -> list[ConfigSubentryData]:
    """Mock subentries."""
    return [
        ConfigSubentryData(
            data={CONF_LINE: "C3", CONF_STOP_ID: 100},
            subentry_id="stop_1",
            subentry_type=SUBENTRY_TYPE_STOP,
            title="C3 - Stop 100",
            unique_id="C3_100",
        )
    ]


@pytest.fixture
def mock_config_entry(
    mock_subentries: list[ConfigSubentryData],
) -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Data Grand Lyon",
        data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        subentries_data=mock_subentries,
    )
