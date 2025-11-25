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
    """
    Set up the Entity Migration integration in the provided HomeAssistant instance and wait for any pending tasks to complete.
    """
    assert await async_setup_component(hass, "entity_migration", {})
    await hass.async_block_till_done()


@pytest.fixture
def mock_automations_with_entity() -> Generator[MagicMock]:
    """
    Provide a MagicMock that replaces the automations_with_entity helper used by tests.
    
    Returns:
        MagicMock: Mock configured to return an empty list when called.
    """
    with patch(
        "homeassistant.components.entity_migration.scanner.automation.automations_with_entity"
    ) as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def mock_scripts_with_entity() -> Generator[MagicMock]:
    """
    Provide a MagicMock that patches scripts_with_entity to return an empty list.
    
    Returns:
        MagicMock: Mock patched at
        `homeassistant.components.entity_migration.scanner.script.scripts_with_entity`
        which returns an empty list when called.
    """
    with patch(
        "homeassistant.components.entity_migration.scanner.script.scripts_with_entity"
    ) as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def mock_scenes_with_entity() -> Generator[MagicMock]:
    """
    Patch homeassistant.components.entity_migration.scanner.scene.scenes_with_entity to return an empty list for tests.
    
    Yields a MagicMock object that has been patched in place; the mock's return value is set to an empty list so calls to the patched function produce no scenes.
    
    Returns:
        MagicMock: The patched mock object whose call returns an empty list.
    """
    with patch(
        "homeassistant.components.entity_migration.scanner.scene.scenes_with_entity"
    ) as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def mock_groups_with_entity() -> Generator[MagicMock]:
    """
    Provide a fixture that patches the groups_with_entity helper to always return an empty list.
    
    Returns:
        MagicMock: The mock object that replaces `groups_with_entity`; calling it returns an empty list.
    """
    with patch(
        "homeassistant.components.entity_migration.scanner.group.groups_with_entity"
    ) as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def mock_persons_with_entity() -> Generator[MagicMock]:
    """
    Patch homeassistant.components.entity_migration.scanner.person.persons_with_entity to return an empty list and yield the mock.
    
    Returns:
        MagicMock: The patched `persons_with_entity` mock with its return value set to an empty list.
    """
    with patch(
        "homeassistant.components.entity_migration.scanner.person.persons_with_entity"
    ) as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def mock_lovelace_data() -> Generator[MagicMock]:
    """
    Provide a patched LOVELACE_DATA value for tests.
    
    Patches homeassistant.components.entity_migration.scanner.LOVELACE_DATA to the string "lovelace" for the duration of the fixture.
    
    Returns:
        The patched LOVELACE_DATA value (the string "lovelace").
    """
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
    """
    Provide a dictionary of mocked helper functions used in entity migration tests.
    
    Returns:
        dict[str, MagicMock]: Mapping of helper names to their MagicMock instances with keys
            "automations", "scripts", "scenes", "groups", and "persons".
    """
    return {
        "automations": mock_automations_with_entity,
        "scripts": mock_scripts_with_entity,
        "scenes": mock_scenes_with_entity,
        "groups": mock_groups_with_entity,
        "persons": mock_persons_with_entity,
    }