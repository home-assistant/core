"""Senziio test fixtures."""

import pytest

from homeassistant.components.senziio import DOMAIN

from . import A_DEVICE_ID, A_FRIENDLY_NAME, ENTRY_DATA

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry():
    """Mock a Senziio device config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=A_FRIENDLY_NAME,
        unique_id=A_DEVICE_ID,
        data=ENTRY_DATA,
    )
