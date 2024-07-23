"""Test fixtures for Azure DevOps."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.azure_devops.const import DOMAIN

from . import DEVOPS_BUILD, DEVOPS_PROJECT, FIXTURE_USER_INPUT, PAT, UNIQUE_ID

from tests.common import MockConfigEntry


@pytest.fixture
async def mock_devops_client() -> AsyncGenerator[MagicMock, None]:
    """Mock the Azure DevOps client."""

    with (
        patch(
            "homeassistant.components.azure_devops.DevOpsClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.azure_devops.config_flow.DevOpsClient",
            new=mock_client,
        ),
    ):
        devops_client = mock_client.return_value
        devops_client.authorized = True
        devops_client.pat = PAT
        devops_client.authorize.return_value = True
        devops_client.get_project.return_value = DEVOPS_PROJECT
        devops_client.get_builds.return_value = [DEVOPS_BUILD]
        devops_client.get_build.return_value = DEVOPS_BUILD
        devops_client.get_work_items_ids_all.return_value = None
        devops_client.get_work_items.return_value = None

        yield devops_client


@pytest.fixture
async def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=FIXTURE_USER_INPUT,
        unique_id=UNIQUE_ID,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.azure_devops.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
