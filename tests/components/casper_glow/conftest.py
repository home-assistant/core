"""Casper Glow session fixtures."""

import pytest

from homeassistant.components.casper_glow.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from . import CASPER_GLOW_DISCOVERY_INFO, setup_integration

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Casper Glow config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Jar",
        data={CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address},
        unique_id=format_mac(CASPER_GLOW_DISCOVERY_INFO.address),
    )


@pytest.fixture
async def config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up a Casper Glow config entry."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry
