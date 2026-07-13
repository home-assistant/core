"""Test fixtures for volkszaehler."""

import pytest

from homeassistant.components.volkszaehler.const import DOMAIN, SUBENTRY_TYPE_CHANNEL
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_UUID

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Fixture for a config entry with one existing channel subentry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="localhost",
        data={
            CONF_HOST: "localhost",
            CONF_PORT: 80,
        },
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_CHANNEL,
                title="existing-uuid",
                data={CONF_UUID: "existing-uuid"},
                unique_id="existing-uuid",
                subentry_id="existing-subentry-id",
            )
        ],
    )
