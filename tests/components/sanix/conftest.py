"""Sanix tests configuration."""

from unittest.mock import MagicMock, patch

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
        domain=DOMAIN, title="Sanix", data={CONF_SERIAL_NO: "1234", CONF_TOKEN: "abcd"}
    )
