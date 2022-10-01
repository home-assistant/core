"""Test helpers for Tibber."""
import pytest

from homeassistant.components.tibber.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry(hass):
    """Tibber config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: "token"},
        unique_id="tibber",
    )
    config_entry.add_to_hass(hass)
    return config_entry
