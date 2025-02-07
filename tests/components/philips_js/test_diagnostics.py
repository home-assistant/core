"""Test the Philips TV diagnostics platform."""

from unittest.mock import AsyncMock

from haphilipsjs.typing import ChannelListType, ContextType, FavoriteListType
from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

TV_CONTEXT = ContextType(level1="NA", level2="NA", level3="NA", data="NA")
TV_CHANNEL_LISTS = {
    "all": ChannelListType(
        version=2,
        id="all",
        listType="MixedSources",
        medium="mixed",
        operator="None",
        installCountry="Poland",
        Channel=[],
    )
}
TV_FAVORITE_LISTS = {
    "1": FavoriteListType(
        version="60",
        id="1",
        type="MixedSources",
        medium="mixed",
        name="Favourites 1",
        channels=[],
    )
}


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_tv: AsyncMock,
) -> None:
    """Test config entry diagnostics."""
    mock_tv.context = TV_CONTEXT
    mock_tv.ambilight_topology = None
    mock_tv.ambilight_mode_raw = "internal"
    mock_tv.ambilight_modes = ["internal", "manual", "expert", "lounge"]
    mock_tv.ambilight_power_raw = {"power": "On"}
    mock_tv.ambilight_power = "On"
    mock_tv.ambilight_measured = None
    mock_tv.ambilight_processed = None
    mock_tv.screenstate = "On"
    mock_tv.channel = None
    mock_tv.channel_lists = TV_CHANNEL_LISTS
    mock_tv.favorite_lists = TV_FAVORITE_LISTS

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot(exclude=props("entry_id", "created_at", "modified_at"))
