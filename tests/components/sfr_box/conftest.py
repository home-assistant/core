"""Provide common SFR Box fixtures."""
import pytest

from homeassistant.components.sfr_box.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def get_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Create and register mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={CONF_HOST: "192.168.0.1"},
        unique_id="e4:5d:51:00:11:22",
        options={},
        entry_id="123456",
    )
    config_entry.add_to_hass(hass)
    return config_entry
