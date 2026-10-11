"""Test INDI Allsky Media Source."""

from unittest.mock import AsyncMock, patch

from aioindiallsky import ImageItem, IndiAllSkyError, MediaData, MonthItem, VideoItem
import pytest

from homeassistant.components.indi_allsky.const import DOMAIN
from homeassistant.components.media_player import BrowseError, MediaType
from homeassistant.components.media_source import (
    URI_SCHEME,
    PlayMedia,
    Unresolvable,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
async def setup_media_source(hass: HomeAssistant) -> None:
    """Set up media source component."""
    assert await async_setup_component(hass, "media_source", {})


async def test_async_resolve_media_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test resolving media to a playable URL."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_indi_allsky_client.get_media_url.return_value = (
        "https://127.0.0.1:443/indi-allsky/images/test.mp4"
    )

    resolved = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#images/test.mp4",
        None,
    )
    assert resolved == PlayMedia(
        "https://127.0.0.1:443/indi-allsky/images/test.mp4", "video/mp4"
    )

    # Test resolving JPEG image located within a timelapse directory
    mock_indi_allsky_client.get_media_url.return_value = (
        "https://127.0.0.1:443/indi-allsky/images/timelapse/20261011/keogram.jpg"
    )
    resolved_keo = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#images/timelapse/20261011/keogram.jpg",
        None,
    )
    assert resolved_keo == PlayMedia(
        "https://127.0.0.1:443/indi-allsky/images/timelapse/20261011/keogram.jpg",
        "image/jpeg",
    )


async def test_async_resolve_media_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test error cases when resolving media items."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Incomplete identifier
    with pytest.raises(Unresolvable):
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/invalid_identifier",
            None,
        )

    # Unknown config entry
    with pytest.raises(Unresolvable):
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/unknown_entry_id#media#test.mp4",
            None,
        )

    # Entry from another domain
    other_entry = MockConfigEntry(domain="other_domain", data={})
    other_entry.add_to_hass(hass)
    with pytest.raises(Unresolvable):
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/{other_entry.entry_id}#media#test.mp4",
            None,
        )

    # Unloaded config entry
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(Unresolvable):
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#test.mp4",
            None,
        )


async def test_async_resolve_media_redirect_resolution(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test resolving latest media with redirect resolution."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_indi_allsky_client.get_media_url.return_value = (
        "https://127.0.0.1:443/indi-allsky/latestimage"
    )

    # Successful redirect with relative location
    aioclient_mock.get(
        "https://127.0.0.1:443/indi-allsky/latestimage",
        status=302,
        headers={"Location": "/indi-allsky/images/captured_1234.jpg"},
    )
    resolved = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#latestimage",
        None,
    )
    assert resolved == PlayMedia(
        "https://127.0.0.1/indi-allsky/images/captured_1234.jpg",
        "image/jpeg",
    )

    # Latest timelapse resolves to video/mp4
    mock_indi_allsky_client.get_media_url.return_value = (
        "https://127.0.0.1:443/indi-allsky/latesttimelapse"
    )
    aioclient_mock.get(
        "https://127.0.0.1:443/indi-allsky/latesttimelapse",
        status=200,
    )
    resolved_tl = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#latesttimelapse",
        None,
    )
    assert resolved_tl == PlayMedia(
        "https://127.0.0.1:443/indi-allsky/latesttimelapse",
        "video/mp4",
    )

    # Redirect error fallback (ClientError or TimeoutError) keeps original url
    mock_indi_allsky_client.get_media_url.return_value = (
        "https://127.0.0.1:443/indi-allsky/latestkeogram"
    )
    aioclient_mock.get(
        "https://127.0.0.1:443/indi-allsky/latestkeogram",
        exc=TimeoutError(),
    )
    resolved_fallback = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#latestkeogram",
        None,
    )
    assert resolved_fallback == PlayMedia(
        "https://127.0.0.1:443/indi-allsky/latestkeogram",
        "image/jpeg",
    )

    # Respect verify_ssl=False setting
    entry_no_verify = MockConfigEntry(
        domain=DOMAIN,
        data={**mock_config_entry.data, CONF_VERIFY_SSL: False},
    )
    entry_no_verify.add_to_hass(hass)
    await hass.config_entries.async_setup(entry_no_verify.entry_id)
    await hass.async_block_till_done()

    mock_indi_allsky_client.get_media_url.return_value = (
        "https://127.0.0.1:443/indi-allsky/lateststartrail"
    )
    aioclient_mock.get(
        "https://127.0.0.1:443/indi-allsky/lateststartrail",
        status=302,
        headers={"Location": "/indi-allsky/images/startrail_1234.jpg"},
    )
    with patch(
        "homeassistant.components.indi_allsky.media_source.async_get_clientsession",
        wraps=async_get_clientsession,
    ) as mock_get_session:
        resolved_no_verify = await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/{entry_no_verify.entry_id}#media#lateststartrail",
            None,
        )
        assert mock_get_session.call_args.kwargs["verify_ssl"] is False

    assert resolved_no_verify == PlayMedia(
        "https://127.0.0.1/indi-allsky/images/startrail_1234.jpg",
        "image/jpeg",
    )


async def test_async_resolve_media_mime_types(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test resolving media with different file extensions and fallback MIME type."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # public/ path format
    mock_indi_allsky_client.get_media_url.return_value = (
        "https://127.0.0.1:443/indi-allsky/public/video.webm"
    )
    res_webm = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#public/video.webm",
        None,
    )
    assert res_webm.mime_type == "video/webm"

    # Unknown extension falls back to image/jpeg
    mock_indi_allsky_client.get_media_url.return_value = (
        "https://127.0.0.1:443/indi-allsky/unknown.unknownext"
    )
    res_fallback = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#unknown.unknownext",
        None,
    )
    assert res_fallback.mime_type == "image/jpeg"


async def test_async_browse_media_root(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test browsing root and instance categories."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # An unloaded entry should not be listed in root
    unloaded_entry = MockConfigEntry(domain=DOMAIN, data={})
    unloaded_entry.add_to_hass(hass)

    await hass.async_block_till_done()

    # Root level: Lists only loaded configured instances
    res_root = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    assert res_root.domain == DOMAIN
    assert res_root.identifier == ""
    assert res_root.title == "INDI Allsky"
    assert len(res_root.children) == 1
    assert res_root.children[0].identifier == mock_config_entry.entry_id

    # Instance level: Lists 3 categories (Latest Media, Videos, Images)
    res_instance = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}"
    )
    assert len(res_instance.children) == 3
    cat_ids = [c.identifier for c in res_instance.children]
    assert f"{mock_config_entry.entry_id}#latest" in cat_ids
    assert f"{mock_config_entry.entry_id}#videos" in cat_ids
    assert f"{mock_config_entry.entry_id}#images" in cat_ids

    # Invalid category raises BrowseError
    with pytest.raises(BrowseError):
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#unknown_category"
        )

    # Browsing unloaded entry raises BrowseError
    with pytest.raises(BrowseError):
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/{unloaded_entry.entry_id}"
        )

    # Malformed numeric date path segments raise BrowseError
    with pytest.raises(BrowseError):
        await async_browse_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#videos#invalid_year",
        )
    with pytest.raises(BrowseError):
        await async_browse_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#images#2026#invalid_month",
        )


async def test_async_browse_latest_media(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test browsing Latest Media category with snapshot, keogram, and star trail."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.latest_keogram = MediaData(
        media_type="keogram",
        filename="images/latest_keogram.jpg",
        day_date="20261011",
        night=True,
        camera_id=1,
    )
    coordinator.latest_startrail = MediaData(
        media_type="startrail",
        filename="images/latest_startrail.jpg",
        day_date="20261011",
        night=True,
        camera_id=1,
    )

    res_latest = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#latest"
    )
    assert len(res_latest.children) == 4
    titles = [c.title for c in res_latest.children]
    assert "Latest Snapshot" in titles
    assert "Latest Keogram" in titles
    assert "Latest Star Trail" in titles
    assert "Latest Timelapse" in titles


async def test_async_browse_videos_hierarchy(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test browsing Videos hierarchy: Years -> Months -> Video items."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_indi_allsky_client.get_video_years.return_value = [2026, 2025]
    mock_indi_allsky_client.get_video_months.return_value = [
        MonthItem(month=10, name="October"),
        MonthItem(month=9, name="September"),
    ]
    mock_indi_allsky_client.get_videos.return_value = [
        VideoItem(
            id=10,
            url="images/timelapse20261011.mp4",
            day_date="20261011",
            day_date_long="October 11, 2026",
            night=True,
            success=True,
            keogram_url="images/keogram20261011.jpg",
            startrail_url="images/startrail20261011.jpg",
        ),
        VideoItem(
            id=11,
            url="images/timelapse_failed.mp4",
            day_date="20261011",
            day_date_long="October 11, 2026",
            night=False,
            success=False,
        ),
    ]
    mock_indi_allsky_client.get_media_url.side_effect = lambda p: (
        f"https://127.0.0.1/{p}"
    )

    res_years = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#videos"
    )
    assert len(res_years.children) == 2
    assert res_years.children[0].title == "2026"
    assert res_years.children[1].title == "2025"

    res_months = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#videos#2026"
    )
    assert len(res_months.children) == 2
    assert res_months.children[0].title == "October"

    res_videos = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#videos#2026#10"
    )
    assert len(res_videos.children) == 3
    titles = [c.title for c in res_videos.children]
    assert "Night Timelapse - October 11, 2026" in titles
    assert "Night Keogram - October 11, 2026" in titles
    assert "Night Star Trail - October 11, 2026" in titles


async def test_async_browse_images_hierarchy(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test browsing Images hierarchy: Years -> Months -> Days -> Hours -> Images."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_indi_allsky_client.get_image_years.return_value = [2026]
    mock_indi_allsky_client.get_image_months.return_value = [
        MonthItem(month=10, name="October")
    ]
    mock_indi_allsky_client.get_image_days.return_value = [11, 10]
    mock_indi_allsky_client.get_image_hours.return_value = [20, 19]
    mock_indi_allsky_client.get_images.return_value = [
        ImageItem(
            id=101,
            url="images/img_200000.jpg",
            timestamp=1791710881,
            time_str="20:00:00",
            width=4056,
            height=3140,
        )
    ]
    mock_indi_allsky_client.get_media_url.side_effect = lambda p: (
        f"https://127.0.0.1/{p}"
    )

    res_years = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#images"
    )
    assert len(res_years.children) == 1
    assert res_years.children[0].title == "2026"

    res_months = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#images#2026"
    )
    assert len(res_months.children) == 1
    assert res_months.children[0].title == "October"

    res_days = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#images#2026#10"
    )
    assert len(res_days.children) == 2
    assert res_days.children[0].title == "Day 11"

    res_hours = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#images#2026#10#11"
    )
    assert len(res_hours.children) == 2
    assert res_hours.children[0].title == "20:00 - 20:59"

    res_images = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#images#2026#10#11#20"
    )
    assert len(res_images.children) == 1
    assert "20:00:00 (4056x3140)" in res_images.children[0].title
    assert res_images.children[0].media_content_type == MediaType.IMAGE


async def test_async_browse_catalog_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test catalog API failures raise BrowseError."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_indi_allsky_client.get_video_years.side_effect = IndiAllSkyError(
        "Communication failed"
    )

    with pytest.raises(BrowseError):
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#videos"
        )
