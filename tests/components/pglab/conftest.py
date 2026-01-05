"""Common fixtures for the PG LAB Electronics tests."""

import pytest

from homeassistant.components.pglab.const import DISCOVERY_TOPIC, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, mock_device_registry, mock_registry

CONF_DISCOVERY_PREFIX = "discovery_prefix"


@pytest.fixture
def device_reg(hass: HomeAssistant):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass: HomeAssistant):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture
async def setup_pglab(hass: HomeAssistant):
    """Set up PG LAB Electronics."""
    hass.config.components.add("pglab")

    entry = MockConfigEntry(
        data={CONF_DISCOVERY_PREFIX: DISCOVERY_TOPIC},
        domain=DOMAIN,
        title="PG LAB Electronics",
    )

    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "pglab" in hass.config.components
