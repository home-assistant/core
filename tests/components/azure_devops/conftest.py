"""Test fixtures for Azure DevOps."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.azure_devops.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import DEVOPS_BUILD, DEVOPS_PROJECT, FIXTURE_USER_INPUT, PAT, UNIQUE_ID

from tests.common import MockConfigEntry


@pytest.fixture
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=FIXTURE_USER_INPUT,
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    return entry


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
async def init_integration(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_devops_client: MagicMock,
) -> MockConfigEntry:
    """Set up the WLED integration for testing."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Let some time pass so coordinators can be reliably triggered by bumping
    # time by SCAN_INTERVAL
    freezer.tick(1)

    return mock_config_entry
