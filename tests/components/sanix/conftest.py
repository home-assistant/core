"""Sanix tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sanix.models import Measurement

from homeassistant.components.sanix.const import CONF_SERIAL_NO, DOMAIN
from homeassistant.const import CONF_TOKEN

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_sanix():
    """Build a fixture for the Sanix API that connects successfully and returns measurements."""
    fixture = load_json_object_fixture("sanix/get_measurements.json")
    mock_sanix_api = MagicMock()
    with (
        patch(
            "homeassistant.components.sanix.config_flow.Sanix",
            return_value=mock_sanix_api,
        ) as mock_sanix_api,
        patch(
            "homeassistant.components.sanix.Sanix",
            return_value=mock_sanix_api,
        ),
    ):
        mock_sanix_api.return_value.fetch_data.return_value = Measurement(**fixture)
        yield mock_sanix_api


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Sanix",
        unique_id="1810088",
        data={CONF_SERIAL_NO: "1234", CONF_TOKEN: "abcd"},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sanix.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
