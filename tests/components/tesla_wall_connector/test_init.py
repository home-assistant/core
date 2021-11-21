"""Test the Tesla Wall Connector config flow."""
from tesla_wall_connector.exceptions import WallConnectorConnectionError

from homeassistant import config_entries
from homeassistant.components.tesla_wall_connector.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import create_wall_connector_entry


async def test_init_success(hass: HomeAssistant) -> None:
    """Test setup and that we get the device info, including firmware version."""

    entry = await create_wall_connector_entry(hass)

    assert entry.state == config_entries.ConfigEntryState.LOADED
    assert hass.data[DOMAIN]
    assert hass.data[DOMAIN][entry.entry_id]


async def test_init_while_offline(hass: HomeAssistant) -> None:
    """Test init with the wall connector offline."""
    entry = await create_wall_connector_entry(
        hass, side_effect=WallConnectorConnectionError
    )

    assert entry.state == config_entries.ConfigEntryState.SETUP_RETRY
    assert entry.entry_id not in hass.data[DOMAIN]


async def test_load_unload(hass):
    """Config entry can be unloaded."""

    entry = await create_wall_connector_entry(hass)

    assert entry.state is config_entries.ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
