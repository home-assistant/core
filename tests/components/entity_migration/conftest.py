"""Fixtures for Entity Migration integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def stub_blueprint_populate(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
async def init_integration(hass: HomeAssistant) -> None:
    """Set up the Entity Migration integration for testing."""
    assert await async_setup_component(hass, "entity_migration", {})
    await hass.async_block_till_done()


@pytest.fixture
def mock_automations_with_entity() -> Generator[MagicMock]:
    """Mock automations_with_entity function."""
    with patch(
        "homeassistant.components.entity_migration.scanner.automation.automations_with_entity"
    ) as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def mock_scripts_with_entity() -> Generator[MagicMock]:
    """Mock scripts_with_entity function."""
    with patch(
        "homeassistant.components.entity_migration.scanner.script.scripts_with_entity"
    ) as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def mock_scenes_with_entity() -> Generator[MagicMock]:
    """Mock scenes_with_entity function."""
    with patch(
        "homeassistant.components.entity_migration.scanner.scene.scenes_with_entity"
    ) as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def mock_groups_with_entity() -> Generator[MagicMock]:
    """Mock groups_with_entity function."""
    with patch(
        "homeassistant.components.entity_migration.scanner.group.groups_with_entity"
    ) as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def mock_persons_with_entity() -> Generator[MagicMock]:
    """Mock persons_with_entity function."""
    with patch(
        "homeassistant.components.entity_migration.scanner.person.persons_with_entity"
    ) as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def mock_lovelace_data() -> Generator[MagicMock]:
    """Mock lovelace data."""
    with patch(
        "homeassistant.components.entity_migration.scanner.LOVELACE_DATA",
        "lovelace",
    ):
        yield


@pytest.fixture
def mock_all_helpers(
    mock_automations_with_entity: MagicMock,
    mock_scripts_with_entity: MagicMock,
    mock_scenes_with_entity: MagicMock,
    mock_groups_with_entity: MagicMock,
    mock_persons_with_entity: MagicMock,
) -> dict[str, MagicMock]:
    """Mock all helper functions."""
    return {
        "automations": mock_automations_with_entity,
        "scripts": mock_scripts_with_entity,
        "scenes": mock_scenes_with_entity,
        "groups": mock_groups_with_entity,
        "persons": mock_persons_with_entity,
    }
