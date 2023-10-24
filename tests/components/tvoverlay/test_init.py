"""Test init of TvOverlay integration."""

from tvoverlay.exceptions import ConnectError

from homeassistant.components.tvoverlay.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import CONF_CONFIG_FLOW, HOST, mocked_tvoverlay_info

from tests.common import MockConfigEntry


async def test_config_not_ready(hass: HomeAssistant) -> None:
    """Test for setup failure with unreachable host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_CONFIG_FLOW,
        unique_id=HOST,
    )
    with mocked_tvoverlay_info() as tvmock:
        tvmock.side_effect = ConnectError
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY
