"""Tests for WATERCryst BIOCAT sensors."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from .common import InitIntegrationFunc
from .conftest import basic_info_response


@pytest.mark.usefixtures("setup_integration")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_mandatory_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    init_integration: InitIntegrationFunc,
) -> None:
    """Test mandatory sensor entities."""

    mock_api_client.get_device_info.return_value = basic_info_response()

    assert await init_integration()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
