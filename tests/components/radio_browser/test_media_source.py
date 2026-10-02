"""Tests for radio_browser media_source."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aiodns.error import DNSError
import pytest
from radios import FilterBy, Order, RadioBrowserError

from homeassistant.components import media_source
from homeassistant.components.media_player import BrowseError, SearchMediaQuery
from homeassistant.components.media_source import MediaSourceItem
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
    assert item.can_search is True

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

        assert mock_config_entry.state is ConfigEntryState.LOADED

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

        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

        with pytest.raises(BrowseError) as exc_info:
            await media_source.async_browse_media(
                hass, f"{media_source.URI_SCHEME}{DOMAIN}/popular"
            )
        assert exc_info.value.translation_key == "config_entry_not_ready"


async def test_search_media(
    hass: HomeAssistant, init_integration: AsyncMock, patch_radios
) -> None:
    """Test searching stations."""

    source = await async_get_media_source(hass)
    patch_radios(source)

    result = await source.async_search_media(
        MediaSourceItem(hass, DOMAIN, f"{media_source.URI_SCHEME}{DOMAIN}", None),
        SearchMediaQuery(search_query="my search"),
    )

    source.radios.search.assert_awaited_with(
        name="my search",
        hide_broken=True,
        limit=100,
        order=Order.CLICK_COUNT,
        reverse=True,
    )
    assert len(result.result) == 5


@pytest.mark.parametrize(
    "exception",
    [DNSError, RadioBrowserError],
)
async def test_search_media_exceptions(
    hass: HomeAssistant,
    init_integration: AsyncMock,
    patch_radios,
    exception: Exception,
) -> None:
    """Test search exceptions."""

    source = await async_get_media_source(hass)
    patch_radios(source)

    source.radios.search.side_effect = exception
    with pytest.raises(BrowseError) as exc_info:
        await source.async_search_media(
            MediaSourceItem(hass, DOMAIN, f"{media_source.URI_SCHEME}{DOMAIN}", None),
            SearchMediaQuery(search_query="my search"),
        )
    assert exc_info.value.translation_key == "radio_browser_error"


async def test_search_media_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, patch_radios
) -> None:
    """Test search config entry not ready."""

    with patch(
        "homeassistant.components.radio_browser.RadioBrowser",
        autospec=True,
    ) as mock_browser:
        mock_browser.return_value.stats.side_effect = RadioBrowserError
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    source = await async_get_media_source(hass)
    patch_radios(source)

    with pytest.raises(BrowseError) as exc_info:
        await source.async_search_media(
            MediaSourceItem(hass, DOMAIN, f"{media_source.URI_SCHEME}{DOMAIN}", None),
            SearchMediaQuery(search_query="my search"),
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

        assert mock_config_entry.state is ConfigEntryState.LOADED

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

        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

        with pytest.raises(media_source.Unresolvable) as exc_info:
            await media_source.async_resolve_media(
                hass, f"{media_source.URI_SCHEME}{DOMAIN}/123456", None
            )
        assert exc_info.value.translation_key == "config_entry_not_ready"


async def test_resolve_media_station_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test resolving a station that no longer exists."""

    with patch(
        "homeassistant.components.radio_browser.RadioBrowser",
        autospec=True,
    ) as mock_browser:
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        mock_browser.return_value.station.return_value = None
        with pytest.raises(media_source.Unresolvable) as exc_info:
            await media_source.async_resolve_media(
                hass, f"{media_source.URI_SCHEME}{DOMAIN}/123456", None
            )
        assert exc_info.value.translation_key == "station_not_found"


async def test_resolve_media_unknown_stream_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test resolving a station whose stream type cannot be determined."""

    with patch(
        "homeassistant.components.radio_browser.RadioBrowser",
        autospec=True,
    ) as mock_browser:
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        station = MagicMock(codec="UNKNOWN", url="https://example.com/stream")
        mock_browser.return_value.station.return_value = station
        with pytest.raises(media_source.Unresolvable) as exc_info:
            await media_source.async_resolve_media(
                hass, f"{media_source.URI_SCHEME}{DOMAIN}/123456", None
            )
        assert exc_info.value.translation_key == "unknown_stream_type"
        mock_browser.return_value.station_click.assert_not_called()


@pytest.mark.parametrize(
    ("identifier", "filter_by", "filter_term"),
    [
        ("country/US", FilterBy.COUNTRY_CODE_EXACT, "US"),
        ("language/dutch", FilterBy.LANGUAGE_EXACT, "dutch"),
        ("tag/jazz", FilterBy.TAG_EXACT, "jazz"),
    ],
)
async def test_browsing_stations_by_category(
    hass: HomeAssistant,
    init_integration: AsyncMock,
    patch_radios,
    identifier: str,
    filter_by: FilterBy,
    filter_term: str,
) -> None:
    """Test browsing the stations of a country, language or tag."""
    source = await async_get_media_source(hass)
    patch_radios(source)

    item = await media_source.async_browse_media(
        hass, f"{media_source.URI_SCHEME}{DOMAIN}/{identifier}"
    )

    source.radios.stations.assert_awaited_with(
        filter_by=filter_by,
        filter_term=filter_term,
        hide_broken=True,
        order=Order.NAME,
        reverse=False,
    )
    assert [child.identifier for child in item.children] == ["1", "2", "3", "4", "5"]
    assert item.children[0].can_play is True
    assert item.children[0].media_content_type == "audio/mpeg"


async def test_browsing_languages(
    hass: HomeAssistant, init_integration: AsyncMock, patch_radios
) -> None:
    """Test browsing the list of languages."""
    source = await async_get_media_source(hass)
    patch_radios(source)
    source.radios.languages = AsyncMock(
        return_value=[SimpleNamespace(name="Dutch", favicon="nl.png")]
    )

    item = await media_source.async_browse_media(
        hass, f"{media_source.URI_SCHEME}{DOMAIN}/language"
    )

    source.radios.languages.assert_awaited_with(order=Order.NAME, hide_broken=True)
    assert [child.identifier for child in item.children] == ["language/dutch"]
    assert item.children[0].title == "Dutch"
    assert item.children[0].can_expand is True


async def test_browsing_tags(
    hass: HomeAssistant, init_integration: AsyncMock, patch_radios
) -> None:
    """Test browsing the most used tags, sorted by name."""
    source = await async_get_media_source(hass)
    patch_radios(source)
    source.radios.tags = AsyncMock(
        return_value=[SimpleNamespace(name="pop"), SimpleNamespace(name="jazz")]
    )

    item = await media_source.async_browse_media(
        hass, f"{media_source.URI_SCHEME}{DOMAIN}/tag"
    )

    source.radios.tags.assert_awaited_with(
        hide_broken=True,
        limit=100,
        order=Order.STATION_COUNT,
        reverse=True,
    )
    assert [child.title for child in item.children] == ["Jazz", "Pop"]
    assert [child.identifier for child in item.children] == ["tag/jazz", "tag/pop"]


async def test_browsing_popular_skips_unplayable_stations(
    hass: HomeAssistant, init_integration: AsyncMock, patch_radios
) -> None:
    """Test browsing popular stations leaves out the ones that cannot be played."""
    source = await async_get_media_source(hass)
    patch_radios(source)
    source.radios.stations = AsyncMock(
        return_value=[
            SimpleNamespace(uuid="1", name="Playable", codec="MP3", favicon="", url=""),
            SimpleNamespace(
                uuid="2", name="Unknown codec", codec="UNKNOWN", favicon="", url=""
            ),
            SimpleNamespace(
                uuid="3",
                name="Unknown stream type",
                codec="",
                favicon="",
                url="https://example.com/stream",
            ),
        ]
    )

    item = await media_source.async_browse_media(
        hass, f"{media_source.URI_SCHEME}{DOMAIN}/popular"
    )

    source.radios.stations.assert_awaited_with(
        hide_broken=True,
        limit=250,
        order=Order.CLICK_COUNT,
        reverse=True,
    )
    assert [child.title for child in item.children] == ["Playable"]


async def test_resolve_media(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test resolving a station to its stream, registering the click."""

    with patch(
        "homeassistant.components.radio_browser.RadioBrowser",
        autospec=True,
    ) as mock_browser:
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        mock_browser.return_value.station.return_value = SimpleNamespace(
            uuid="123456",
            codec="MP3",
            url="https://example.com/listen.pls",
            url_resolved="https://example.com/stream.mp3",
        )
        resolved = await media_source.async_resolve_media(
            hass, f"{media_source.URI_SCHEME}{DOMAIN}/123456", None
        )

        assert resolved.url == "https://example.com/stream.mp3"
        assert resolved.mime_type == "audio/mpeg"
        mock_browser.return_value.station_click.assert_awaited_once_with(uuid="123456")
