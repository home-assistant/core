"""Fixtures for the Virtual Remote integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from homeassistant.components.virtual_remote.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
    DOMAIN,
)

from tests.common import MockConfigEntry


INFRARED_ENTITY_ID = "infrared.test_ir"
REMOTE_ID = "living_room_tv"
REMOTE_NAME = "Living Room TV"
RAW_COMMAND = "38000:9000,4500,560,560"


@pytest.fixture
def mock_setup_entry() -> Generator:
    """Mock config entry platform setup."""
    with patch(
        "homeassistant.components.virtual_remote.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_reload() -> Generator:
    """Mock config entry reload."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload",
        return_value=None,
    ) as mock_reload:
        yield mock_reload


@pytest.fixture
def infrared_entity(hass: HomeAssistant) -> str:
    """Register an infrared entity."""
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "infrared",
        "test",
        "ir",
        suggested_object_id="test_ir",
        original_name="Test IR",
    )
    hass.states.async_set(INFRARED_ENTITY_ID, "on")
    return INFRARED_ENTITY_ID


@pytest.fixture
def config_entry(hass: HomeAssistant, infrared_entity: str) -> MockConfigEntry:
    """Create a virtual remote config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Virtual Remote",
        data={},
        options={
            CONF_VIRTUAL_REMOTES: [
                {
                    CONF_REMOTE_ID: REMOTE_ID,
                    CONF_REMOTE_NAME: REMOTE_NAME,
                    CONF_INFRARED_ENTITY_ID: infrared_entity,
                    CONF_REMOTE_COMMANDS: {
                        "POWER_ON": RAW_COMMAND,
                        "POWER_OFF": RAW_COMMAND,
                        "TOGGLE": RAW_COMMAND,
                    },
                }
            ]
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)
    return entry
