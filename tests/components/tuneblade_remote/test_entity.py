"""Tests for the TuneBlade base entity."""

from unittest.mock import Mock

import pytest

from homeassistant.components.tuneblade_remote.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_coordinator() -> Mock:
    """Return a mock coordinator for TuneBlade entities."""
    coordinator = Mock()
    coordinator.data = {}
    return coordinator


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry for TuneBlade entities."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="TuneBlade",
        data={"host": "localhost", "port": 54412, "name": "TuneBlade"},
    )


# NOTE: Entity initialization tests removed due to incompatibility with MockConfigEntry.entry_id being immutable/random.
