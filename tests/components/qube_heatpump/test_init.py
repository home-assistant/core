"""Test the Qube Heat Pump integration init."""

from unittest.mock import MagicMock

from homeassistant.components.qube_heatpump.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_MAC = "00:0a:5c:94:83:15"


async def test_async_setup_entry(
    hass: HomeAssistant, mock_qube_client: MagicMock
) -> None:
    """Test successful setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 502},
        unique_id=MOCK_MAC,
        title="Qube Heat Pump",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_async_unload_entry(
    hass: HomeAssistant, mock_qube_client: MagicMock
) -> None:
    """Test successful unload."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 502},
        unique_id=MOCK_MAC,
        title="Qube Heat Pump",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    mock_qube_client.close.assert_called_once()
