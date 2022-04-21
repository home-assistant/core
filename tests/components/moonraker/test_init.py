"""Tests for the Gree Integration."""
from unittest.mock import Mock, patch

from homeassistant.components.moonraker.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTRY_NAME = "test_host_1"


def get_mock_entry(hass: HomeAssistant, entry_name: str) -> MockConfigEntry:
    """Generate a mock config entry for testing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=entry_name,
        title=entry_name,
        data={
            CONF_HOST: f"{entry_name}.local",
            CONF_PORT: 7125,
            CONF_SSL: False,
            CONF_API_KEY: "",
        },
    )
    entry.add_to_hass(hass)
    return entry


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Complete setup for config entry."""
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_simple(hass: HomeAssistant) -> None:
    """Test gree integration is setup."""
    with patch(
        "homeassistant.components.moonraker.sensor.async_setup_entry",
        return_value=True,
    ) as sensor_setup:
        entry = get_mock_entry(hass, ENTRY_NAME)
        await setup_entry(hass, entry)

        assert len(sensor_setup.mock_calls) == 1
        assert entry.state is ConfigEntryState.LOADED

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0


async def test_unload_config_entry(hass: HomeAssistant, mock_connector: Mock) -> None:
    """Test that the async_unload_entry works."""
    # As we have currently no configuration, we just to pass the domain here.
    entry = get_mock_entry(hass, ENTRY_NAME)
    await setup_entry(hass, entry)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
