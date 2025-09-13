"""Fixtures for Wireless Sensor Tag integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from wirelesstagpy import WirelessTags
from wirelesstagpy.exceptions import WirelessTagsException

from homeassistant.components.wirelesstag.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Wireless Sensor Tags",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
        },
        unique_id="test@example.com",
    )


@pytest.fixture
def mock_tag_data() -> dict[str, Any]:
    """Return mock tag data."""
    return load_json_object_fixture("tags_data.json", DOMAIN)


@pytest.fixture
def mock_wirelesstags_api() -> Generator[Mock]:
    """Mock the WirelessTags API."""
    with patch("homeassistant.components.wirelesstag.api.WirelessTags") as mock_api:
        api_instance = Mock(spec=WirelessTags)
        mock_api.return_value = api_instance

        # Mock successful authentication and data loading
        api_instance.load_tags.return_value = load_json_object_fixture(
            "tags_data.json", DOMAIN
        )

        # Mock arm/disarm methods
        api_instance.arm_temperature = Mock()
        api_instance.disarm_temperature = Mock()
        api_instance.arm_humidity = Mock()
        api_instance.disarm_humidity = Mock()
        api_instance.arm_motion = Mock()
        api_instance.disarm_motion = Mock()
        api_instance.arm_light = Mock()
        api_instance.disarm_light = Mock()
        api_instance.arm_moisture = Mock()
        api_instance.disarm_moisture = Mock()

        # Mock monitoring
        api_instance.start_monitoring = Mock()

        yield api_instance


@pytest.fixture
def mock_wirelesstags_api_auth_error() -> Generator[Mock]:
    """Mock the WirelessTags API with authentication error."""
    with patch("homeassistant.components.wirelesstag.api.WirelessTags") as mock_api:
        mock_api.side_effect = WirelessTagsException("Invalid username or password")
        yield mock_api


@pytest.fixture
def mock_wirelesstags_api_connection_error() -> Generator[Mock]:
    """Mock the WirelessTags API with connection error."""
    with patch("homeassistant.components.wirelesstag.api.WirelessTags") as mock_api:
        mock_api.side_effect = ConnectionError("Connection timeout")
        yield mock_api


@pytest.fixture
def mock_wirelesstags_api_load_error() -> Generator[Mock]:
    """Mock the WirelessTags API with load tags error."""
    with patch("homeassistant.components.wirelesstag.api.WirelessTags") as mock_api:
        api_instance = Mock(spec=WirelessTags)
        mock_api.return_value = api_instance
        api_instance.load_tags.side_effect = WirelessTagsException("API Error")
        yield api_instance


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.wirelesstag.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


class MockTag:
    """Mock tag object for testing."""

    def __init__(self, tag_data: dict[str, Any]) -> None:
        """Initialize mock tag."""
        for key, value in tag_data.items():
            setattr(self, key, value)

    @property
    def human_readable_name(self) -> str:
        """Return human readable name."""
        return self.human_readable_name


@pytest.fixture
def mock_tag() -> MockTag:
    """Return a mock tag object."""
    tag_data = load_json_object_fixture("tags_data.json", DOMAIN)["tag_1"]
    if not isinstance(tag_data, dict):
        raise TypeError("tag_data must be a dict")
    return MockTag(tag_data)


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wirelesstags_api: Mock,
) -> MockConfigEntry:
    """Set up the Wireless Sensor Tag integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wirelesstag.coordinator.WirelessTagAPI"
    ) as mock_api_class:
        mock_api_class.return_value.async_authenticate = AsyncMock(return_value=True)
        mock_api_class.return_value.async_get_tags = AsyncMock(
            return_value=load_json_object_fixture(
                "tags_data.json", DOMAIN
            )
        )
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
