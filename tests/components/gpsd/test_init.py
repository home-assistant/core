"""Test init."""

from unittest.mock import patch

from gps3.agps3threaded import GPSD_PORT as DEFAULT_PORT

from homeassistant.components.gpsd import DEPRECATED_ISSUE_ID, DOMAIN as GPSD_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry

HOST = "gpsd.local"


async def test_repair_issue_is_created(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair issue is created."""
    with patch("homeassistant.components.gpsd.AGPS3mechanism", autospec=True):
        config_entry = MockConfigEntry(
            title="test",
            domain=GPSD_DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: DEFAULT_PORT,
            },
        )

        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.LOADED
        assert (
            HOMEASSISTANT_DOMAIN,
            DEPRECATED_ISSUE_ID,
        ) in issue_registry.issues

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.NOT_LOADED
        assert (
            HOMEASSISTANT_DOMAIN,
            DEPRECATED_ISSUE_ID,
        ) not in issue_registry.issues
