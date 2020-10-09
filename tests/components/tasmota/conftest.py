"""Test fixtures for Tasmota component."""

import pytest

from homeassistant import config_entries
from homeassistant.components.tasmota.const import (
    CONF_DISCOVERY_PREFIX,
    DEFAULT_PREFIX,
    DOMAIN,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry, mock_device_registry, mock_registry


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture(autouse=True)
def disable_debounce():
    """Set MQTT debounce timer to zero."""
    with patch("hatasmota.mqtt.DEBOUNCE_TIMEOUT", 0):
        yield


async def setup_tasmota_helper(hass):
    """Set up Tasmota."""
    hass.config.components.add("tasmota")

    entry = MockConfigEntry(
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        data={CONF_DISCOVERY_PREFIX: DEFAULT_PREFIX},
        domain=DOMAIN,
        title="Tasmota",
    )

    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    assert "tasmota" in hass.config.components


@pytest.fixture
async def setup_tasmota(hass):
    """Set up Tasmota."""
    await setup_tasmota_helper(hass)
