"""Common fixtures for the MELCloud Home tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiomelcloudhome import UserContext
import pytest

from homeassistant.components.melcloud_home.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry, load_json_value_fixture

MOCK_USER_INPUT = {
    CONF_EMAIL: "user@example.com",
    CONF_PASSWORD: "thatyouevenlookedheretoseethepassword",
}


@pytest.fixture
def mock_melcloud_client() -> Generator[AsyncMock]:
    """Mock MELCloud Home client context retrieval."""
    mocked_get_context = AsyncMock(
        return_value=UserContext.model_validate(
            load_json_value_fixture("context.json", DOMAIN)
        )
    )
    with (
        patch(
            "homeassistant.components.melcloud_home.config_flow.MELCloudHome.get_context",
            new=mocked_get_context,
        ),
        patch(
            "homeassistant.components.melcloud_home.coordinator.MELCloudHome.get_context",
            new=mocked_get_context,
        ),
    ):
        yield mocked_get_context


@pytest.fixture
def mock_control_ata_unit() -> Generator[AsyncMock]:
    """Mock MELCloud Home ATA unit control."""
    mock = AsyncMock()
    with patch(
        "homeassistant.components.melcloud_home.coordinator.MELCloudHome.control_ata_unit",
        new=mock,
    ):
        yield mock


@pytest.fixture
def mock_control_atw_unit() -> Generator[AsyncMock]:
    """Mock MELCloud Home ATW unit control."""
    mock = AsyncMock()
    with patch(
        "homeassistant.components.melcloud_home.coordinator.MELCloudHome.control_atw_unit",
        new=mock,
    ):
        yield mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a MELCloud Home config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_USER_INPUT[CONF_EMAIL],
        title=MOCK_USER_INPUT[CONF_EMAIL],
        data=MOCK_USER_INPUT,
    )
