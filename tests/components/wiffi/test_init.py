"""Tests for the wiffi integration setup."""

import errno
from unittest.mock import patch

from homeassistant.components.wiffi.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_start_server_failed(hass: HomeAssistant) -> None:
    """Test setup fails when the server can't be started."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_PORT: 8189})
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wiffi.WiffiTcpServer.start_server",
        side_effect=OSError(errno.EACCES, "Permission denied"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Failed to start the wiffi server on port 8189"
