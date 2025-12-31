"""Fixtures for WaterFurnace integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from waterfurnace.waterfurnace import WFReading

from homeassistant.components.waterfurnace.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.waterfurnace.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_waterfurnace_client() -> Generator[Mock]:
    """Mock WaterFurnace client."""
    with (
        patch(
            "homeassistant.components.waterfurnace.config_flow.WaterFurnace",
            autospec=True,
        ) as mock_client_class,
    ):
        mock_client = mock_client_class.return_value

        # Mock the login method (blocking call)
        mock_client.login = Mock()

        # Mock the read method (blocking call) with fixture data
        device_data = WFReading(load_json_object_fixture("device_data.json", DOMAIN))

        mock_client.read = Mock(return_value=device_data)

        # Mock the GWID property
        mock_client.gwid = "TEST_GWID_12345"

        yield mock_client


@pytest.fixture
def mock_waterfurnace_client_no_gwid(mock_waterfurnace_client: Mock) -> Mock:
    """Mock WaterFurnace client without GWID."""
    mock_waterfurnace_client.gwid = None
    return mock_waterfurnace_client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="WaterFurnace TEST_GWID_12345",
        data={
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
        },
        unique_id="TEST_GWID_12345",
    )
