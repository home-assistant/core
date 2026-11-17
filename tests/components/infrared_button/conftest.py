"""Common fixtures for the Infrared button tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID

from homeassistant.components.infrared_button.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_MODULATION,
    CONF_TIMINGS,
    DOMAIN,
    SUBENTRY_TYPE_COMMAND,
)
from homeassistant.config_entries import ConfigSubentryData

TIMINGS = [9000, -4500, 560, -560]


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.infrared_button.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry with one learned command."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Living room TV",
        entry_id="1234567890",
        data={CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID},
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_COMMAND,
                subentry_id="power_subentry",
                title="Power",
                data={CONF_TIMINGS: TIMINGS, CONF_MODULATION: 38000},
                unique_id=None,
            )
        ],
    )
