"""Test fixtures for the Wallbox integration."""

import pytest

from homeassistant.components.wallbox.const import CONF_STATION, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test_username",
            CONF_PASSWORD: "test_password",
            CONF_STATION: "12345",
        },
        entry_id="testEntry",
    )
    entry.add_to_hass(hass)
    return entry
