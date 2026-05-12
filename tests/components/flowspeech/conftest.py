"""Common fixtures for the FlowSpeech tests."""

import pytest

from homeassistant.components.flowspeech.const import CONF_API_KEY, CONF_VOICE, DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Fixture for a FlowSpeech config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="FlowSpeech",
        data={CONF_API_KEY: "fs_test", CONF_VOICE: "Kore"},
        unique_id="flowspeech",
        entry_id="test-entry-id",
    )
