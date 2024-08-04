"""Tests for the Nextcloud integration."""

from unittest.mock import Mock, patch

from homeassistant.components.nextcloud.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant, config: dict, data: dict
) -> MockConfigEntry:
    """Set up the nextcloud integration."""
    entry = MockConfigEntry(domain=DOMAIN, title=config[CONF_URL], data=config)

    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.nextcloud.NextcloudMonitor",
        ) as mock_nextcloud_monitor,
    ):
        mock_nextcloud_monitor.update = Mock(return_value=True)
        mock_nextcloud_monitor.return_value.data = data
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
