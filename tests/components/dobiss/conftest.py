"""Fixtures for the Dobiss integration tests."""

import pytest

from homeassistant.components.dobiss import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
async def config_entry() -> MockConfigEntry:
    """Return a mock ConfigEntry for dobiss."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Dobiss Gateway",
        data={
            "host": "127.0.0.1",
            "secret": "fake-token",
            "secure": False,
        },
        unique_id="dobiss-1234",
    )
