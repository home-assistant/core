"""Tests for radio_browser media_source."""

from unittest.mock import AsyncMock, patch

from aiodns.error import DNSError
import pytest
from radios import FilterBy, Order, RadioBrowserError

from homeassistant.components import media_source
from homeassistant.components.media_player import BrowseError
from homeassistant.components.radio_browser.media_source import async_get_media_source
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

DOMAIN = "radio_browser"


@pytest.fixture(autouse=True)
async def setup_media_source(hass: HomeAssistant) -> None:
    """Set up media source."""
    assert await async_setup_component(hass, "media_source", {})


async def test_browsing_local(
    hass: HomeAssistant, init_integration: AsyncMock, patch_radios
) -> None:
    """Test browsing local stations."""

    hass.config.latitude = 45.58539
    hass.config.longitude = -122.40320
    hass.config.country = "US"

    source = await async_get_media_source(hass)
    patch_radios(source)

    item = await media_source.async_browse_media(
        hass, f"{media_source.URI_SCHEME}{DOMAIN}"
    )

    assert item is not None
    assert item.title == "My Radios"
    assert item.children is not None
    assert len(item.children) == 5
    assert item.can_play is False
    assert item.can_expand is True

    assert item.children[3].title == "Local stations"

    item_child = await media_source.async_browse_media(
        hass, item.children[3].media_content_id
    )

    source.radios.stations.assert_awaited_with(
        filter_by=FilterBy.COUNTRY_CODE_EXACT,
        filter_term=hass.config.country,
        hide_broken=True,
        order=Order.NAME,
        reverse=False,
    )

    assert item_child is not None
    assert item_child.title == "My Radios"
    assert len(item_child.children) == 2
    assert item_child.children[0].title == "Near Station 1"
    assert item_child.children[1].title == "Near Station 2"

    # Test browsing a different category to hit the path where async_build_local
    # returns []
    other_browse = await media_source.async_browse_media(
        hass, f"{media_source.URI_SCHEME}{DOMAIN}/nonexistent"
    )

    assert other_browse is not None
    assert other_browse.title == "My Radios"
    assert len(other_browse.children) == 0


@pytest.mark.parametrize(
    "exception",
    [DNSError, RadioBrowserError],
)
async def test_browsing_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test browsing exceptions."""

    with patch(
        "homeassistant.components.radio_browser.RadioBrowser",
        autospec=True,
    ) as mock_browser:
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.LOADED

        mock_browser.return_value.stations.side_effect = exception
        with pytest.raises(BrowseError) as exc_info:
            await media_source.async_browse_media(
                hass, f"{media_source.URI_SCHEME}{DOMAIN}/popular"
            )
        assert exc_info.value.translation_key == "radio_browser_error"


async def test_browsing_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test browsing config entry not ready."""

    with patch(
        "homeassistant.components.radio_browser.RadioBrowser",
        autospec=True,
    ) as mock_browser:
        mock_browser.return_value.stats.side_effect = RadioBrowserError
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY

        with pytest.raises(BrowseError) as exc_info:
            await media_source.async_browse_media(
                hass, f"{media_source.URI_SCHEME}{DOMAIN}/popular"
            )
        assert exc_info.value.translation_key == "config_entry_not_ready"


@pytest.mark.parametrize(
    "exception",
    [DNSError, RadioBrowserError],
)
async def test_resolve_media_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test resolving media exceptions."""

    with patch(
        "homeassistant.components.radio_browser.RadioBrowser",
        autospec=True,
    ) as mock_browser:
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.LOADED

        mock_browser.return_value.station.side_effect = exception
        with pytest.raises(media_source.Unresolvable) as exc_info:
            await media_source.async_resolve_media(
                hass, f"{media_source.URI_SCHEME}{DOMAIN}/123456", None
            )
        assert exc_info.value.translation_key == "radio_browser_error"


async def test_resolve_media_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test resolving media config entry not ready."""

    with patch(
        "homeassistant.components.radio_browser.RadioBrowser",
        autospec=True,
    ) as mock_browser:
        mock_browser.return_value.stats.side_effect = RadioBrowserError
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY

        with pytest.raises(media_source.Unresolvable) as exc_info:
            await media_source.async_resolve_media(
                hass, f"{media_source.URI_SCHEME}{DOMAIN}/123456", None
            )
        assert exc_info.value.translation_key == "config_entry_not_ready"
