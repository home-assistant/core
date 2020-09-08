"""Test fixtures for Tasmota component."""

import pytest

from homeassistant import config_entries
from homeassistant.components import tasmota
from homeassistant.components.tasmota.const import CONF_DISCOVERY_PREFIX, DEFAULT_PREFIX

from tests.common import MockConfigEntry, mock_device_registry, mock_registry


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


async def setup_tasmota(hass, entry=None):
    """Set up Tasmota."""
    hass.config.components.add("tasmota")

    if entry is None:
        entry = MockConfigEntry(
            connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
            data={CONF_DISCOVERY_PREFIX: DEFAULT_PREFIX},
            domain=tasmota.DOMAIN,
            title="Tasmota",
        )

        entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    assert "tasmota" in hass.config.components
