"""Test configuration for ping."""
from unittest.mock import patch

from icmplib import Host
import pytest

from homeassistant.components.device_tracker.const import CONF_CONSIDER_HOME
from homeassistant.components.ping import DOMAIN
from homeassistant.components.ping.const import CONF_PING_COUNT
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def patch_setup(*args, **kwargs):
    """Patch setup methods."""
    with patch(
        "homeassistant.components.ping.async_setup_entry",
        return_value=True,
    ), patch("homeassistant.components.ping.async_setup", return_value=True):
        yield


@pytest.fixture(autouse=True)
async def patch_ping():
    """Patch icmplib async_ping."""
    mock = Host("10.10.10.10", 5, [10, 1, 2])

    with patch(
        "homeassistant.components.ping.helpers.async_ping", return_value=mock
    ), patch("homeassistant.components.ping.async_ping", return_value=mock):
        yield mock


@pytest.fixture(name="config_entry")
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a MockConfigEntry for testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="10.10.10.10",
        options={
            CONF_HOST: "10.10.10.10",
            CONF_PING_COUNT: 10.0,
            CONF_CONSIDER_HOME: 180,
        },
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, patch_ping
) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
