"""Test INDI Allsky Media Source."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import gzip
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError, client_exceptions
from aioindiallsky import ImageItem, IndiAllSkyError, MediaData, MonthItem, VideoItem
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.indi_allsky.const import DOMAIN
from homeassistant.components.media_player import BrowseError, MediaType
from homeassistant.components.media_source import (
    URI_SCHEME,
    PlayMedia,
    Unresolvable,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.setup import async_setup_component


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

    proxy_url = (
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/aW1hZ2VzL3Rlc3QubXA0"
    )
    resolved = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#images/test.mp4",
        None,
    )
    assert resolved == PlayMedia(proxy_url, "video/mp4")

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
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/aW1hZ2VzL3RpbWVsYXBzZS8yMDI2MTAxMS9rZW9ncmFtLmpwZw==",
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
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0aW1hZ2U=",
        "image/jpeg",
    )

    # Latest timelapse with unknown extension falls back to video/mp4
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
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0dGltZWxhcHNl",
        "video/mp4",
    )

    # Extensionless latest endpoint returning 200 preserves direct Content-Type (e.g. video/webm)
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "https://127.0.0.1:443/indi-allsky/latesttimelapse",
        status=200,
        headers={"Content-Type": "video/webm; charset=utf-8"},
    )
    resolved_tl_direct_ct = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#latesttimelapse",
        None,
    )
    assert resolved_tl_direct_ct == PlayMedia(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0dGltZWxhcHNl",
        "video/webm",
    )

    # Latest timelapse redirecting to .webm uses detected video/webm
    mock_indi_allsky_client.get_media_url.return_value = (
        "https://127.0.0.1:443/indi-allsky/latesttimelapse"
    )
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "https://127.0.0.1:443/indi-allsky/latesttimelapse",
        status=302,
        headers={"Location": "/indi-allsky/videos/timelapse.webm"},
    )
    resolved_tl_webm = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#latesttimelapse",
        None,
    )
    assert resolved_tl_webm == PlayMedia(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0dGltZWxhcHNl",
        "video/webm",
    )

    # Cross-origin redirect in resolve is rejected, retaining original URL/fallback
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "https://127.0.0.1:443/indi-allsky/latesttimelapse",
        status=302,
        headers={"Location": "http://169.254.169.254/latest/meta-data"},
    )
    resolved_ssrf = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#latesttimelapse",
        None,
    )
    assert resolved_ssrf == PlayMedia(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0dGltZWxhcHNl",
        "video/mp4",
    )

    # Malformed redirect Location header in resolve is ignored safely
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "https://127.0.0.1:443/indi-allsky/latesttimelapse",
        status=302,
        headers={"Location": "http://[invalid-ipv6/path"},
    )
    resolved_malformed_loc = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#latesttimelapse",
        None,
    )
    assert resolved_malformed_loc == PlayMedia(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0dGltZWxhcHNl",
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
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0a2VvZ3JhbQ==",
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
        f"/api/indi_allsky/media/{entry_no_verify.entry_id}/bGF0ZXN0c3RhcnRyYWls",
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
    assert res_webm == PlayMedia(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/cHVibGljL3ZpZGVvLndlYm0=",
        "video/webm",
    )

    # Unknown extension falls back to image/jpeg
    mock_indi_allsky_client.get_media_url.return_value = (
        "https://127.0.0.1:443/indi-allsky/public/unknown.unknownext"
    )
    res_fallback = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#public/unknown.unknownext",
        None,
    )
    assert res_fallback == PlayMedia(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/cHVibGljL3Vua25vd24udW5rbm93bmV4dA==",
        "image/jpeg",
    )


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

    # Unsupported / excess path segments raise BrowseError
    with pytest.raises(BrowseError):
        await async_browse_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#latest#junk",
        )
    with pytest.raises(BrowseError):
        await async_browse_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#videos#2026#10#junk",
        )
    with pytest.raises(BrowseError):
        await async_browse_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#images#2026#10#11#20#extra",
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
    assert (
        res_latest.children[0].thumbnail
        == f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0aW1hZ2U="
    )
    assert (
        res_latest.children[1].thumbnail
        == f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0a2VvZ3JhbQ=="
    )
    assert (
        res_latest.children[2].thumbnail
        == f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0c3RhcnRyYWls"
    )


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
            keogram_url="images/keogram_day_20261011.jpg",
            startrail_url="images/startrail_day_20261011.jpg",
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
    assert len(res_videos.children) == 5
    titles = [c.title for c in res_videos.children]
    assert "Night Timelapse - October 11, 2026" in titles
    assert "Night Keogram - October 11, 2026" in titles
    assert "Night Star Trail - October 11, 2026" in titles
    assert "Day Timelapse - October 11, 2026" not in titles
    assert "Day Keogram - October 11, 2026" in titles
    assert "Day Star Trail - October 11, 2026" in titles
    assert (
        res_videos.children[1].thumbnail
        == f"/api/indi_allsky/media/{mock_config_entry.entry_id}/aW1hZ2VzL2tlb2dyYW0yMDI2MTAxMS5qcGc="
    )
    assert (
        res_videos.children[2].thumbnail
        == f"/api/indi_allsky/media/{mock_config_entry.entry_id}/aW1hZ2VzL3N0YXJ0cmFpbDIwMjYxMDExLmpwZw=="
    )


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
    assert res_images.children[0].thumbnail is None


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


async def test_proxy_view_success_and_headers(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test successful streaming and header handling in proxy view."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    upstream_url = "https://127.0.0.1:443/indi-allsky/images/sample.jpg"
    mock_indi_allsky_client.get_media_url.return_value = upstream_url

    # Trigger async_get_media_source to register view
    await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#images/sample.jpg",
        None,
    )

    client = await hass_client()
    raw_data = b"image-bytes-data"
    compressed_data = gzip.compress(raw_data)
    aioclient_mock.get(
        upstream_url,
        content=compressed_data,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Encoding": "gzip",
            "Content-Length": str(len(compressed_data)),
            "Content-Range": f"bytes 0-{len(compressed_data) - 1}/{len(compressed_data)}",
            "Content-Type": "image/jpeg",
        },
    )

    # b64 for "images/sample.jpg" is "aW1hZ2VzL3NhbXBsZS5qcGc="
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/aW1hZ2VzL3NhbXBsZS5qcGc=",
        headers={"Range": f"bytes=0-{len(compressed_data) - 1}"},
    )
    assert resp.status == 200
    assert resp.headers.get("Content-Type") == "image/jpeg"
    assert resp.headers.get("Content-Security-Policy") == "sandbox"
    assert resp.headers.get("Content-Encoding") == "gzip"
    assert resp.headers.get("Accept-Ranges") == "bytes"
    assert resp.headers.get("Content-Length") == str(len(compressed_data))
    assert resp.headers.get("Content-Range") == (
        f"bytes 0-{len(compressed_data) - 1}/{len(compressed_data)}"
    )
    assert await resp.read() == raw_data


async def test_proxy_view_head_support(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test HEAD requests on proxy view return headers without streaming body."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    upstream_url = "https://127.0.0.1:443/indi-allsky/images/sample.jpg"
    mock_indi_allsky_client.get_media_url.return_value = upstream_url

    await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#images/sample.jpg",
        None,
    )

    client = await hass_client()
    aioclient_mock.head(
        upstream_url,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": "1024",
            "Content-Type": "image/jpeg",
        },
    )

    resp = await client.head(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/aW1hZ2VzL3NhbXBsZS5qcGc=",
    )
    assert resp.status == 200
    assert resp.headers.get("Content-Type") == "image/jpeg"
    assert resp.headers.get("Content-Security-Policy") == "sandbox"
    assert resp.headers.get("Accept-Ranges") == "bytes"
    assert resp.headers.get("Content-Length") == "1024"
    assert await resp.read() == b""


async def test_proxy_view_sandboxes_active_content(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test active content types like SVG or HTML are served with sandbox CSP."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    upstream_url = "https://127.0.0.1:443/indi-allsky/images/vector.svg"
    mock_indi_allsky_client.get_media_url.return_value = upstream_url

    await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#images/vector.svg",
        None,
    )

    client = await hass_client()
    svg_payload = b"<svg><script>alert(1)</script></svg>"
    aioclient_mock.get(
        upstream_url,
        content=svg_payload,
        headers={
            "Content-Length": str(len(svg_payload)),
            "Content-Type": "image/svg+xml",
        },
    )

    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/aW1hZ2VzL3ZlY3Rvci5zdmc=",
    )
    assert resp.status == 200
    assert resp.headers.get("Content-Type") == "image/svg+xml"
    assert resp.headers.get("Content-Security-Policy") == "sandbox"
    assert await resp.read() == svg_payload


async def test_proxy_view_content_type_inference(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test proxy view MIME fallback when Content-Type is missing from upstream."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_indi_allsky_client.get_media_url.return_value = (
        "https://127.0.0.1:443/indi-allsky/images/sample.jpg"
    )
    await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#images/sample.jpg",
        None,
    )

    client = await hass_client()

    # 1. Inferred from extension in url (e.g. .mp4)
    upstream_url_mp4 = "https://127.0.0.1:443/indi-allsky/public/video.mp4"
    mock_indi_allsky_client.get_media_url.return_value = upstream_url_mp4
    aioclient_mock.get(upstream_url_mp4, content=b"video-bytes")

    # b64 for "public/video.mp4" is "cHVibGljL3ZpZGVvLm1wNA=="
    resp_mp4 = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/cHVibGljL3ZpZGVvLm1wNA=="
    )
    assert resp_mp4.status == 200
    assert resp_mp4.headers.get("Content-Type") == "video/mp4"

    # 2. latesttimelapse fallback to video/mp4 when url has no extension
    aioclient_mock.clear_requests()
    upstream_url_tl = "https://127.0.0.1:443/indi-allsky/latesttimelapse"
    mock_indi_allsky_client.get_media_url.return_value = upstream_url_tl
    aioclient_mock.get(upstream_url_tl, content=b"tl-bytes")

    # b64 for "latesttimelapse" is "bGF0ZXN0dGltZWxhcHNl"
    resp_tl = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0dGltZWxhcHNl"
    )
    assert resp_tl.status == 200
    assert resp_tl.headers.get("Content-Type") == "video/mp4"

    # 3. other paths fallback to image/jpeg when url has no extension
    aioclient_mock.clear_requests()
    upstream_url_other = "https://127.0.0.1:443/indi-allsky/public/noext"
    mock_indi_allsky_client.get_media_url.return_value = upstream_url_other
    aioclient_mock.get(upstream_url_other, content=b"img-bytes")

    # b64 for "public/noext" is "cHVibGljL25vZXh0"
    resp_other = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/cHVibGljL25vZXh0"
    )
    assert resp_other.status == 200
    assert resp_other.headers.get("Content-Type") == "image/jpeg"


async def test_proxy_view_errors(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test proxy view error handling."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_indi_allsky_client.get_media_url.return_value = (
        "https://127.0.0.1:443/indi-allsky/images/sample.jpg"
    )
    await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#images/sample.jpg",
        None,
    )

    client = await hass_client()

    # 1. Non-existent entry ID -> 404
    resp = await client.get("/api/indi_allsky/media/nonexistent/c2FtcGxl")
    assert resp.status == 404

    # 2. Invalid base64 path -> 400
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/!invalid_base64!"
    )
    assert resp.status == 400

    # Invalid base64 characters with padding/symbols (e.g. c2FtcGxl$$$$) -> 400
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/c2FtcGxl$$$$"
    )
    assert resp.status == 400

    # Non-ASCII path segment -> 400
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/%C3%A9"
    )
    assert resp.status == 400

    # 3. Path traversal (..) -> 400
    # b64 for "images/../secret" is "aW1hZ2VzLy4uL3NlY3JldA=="
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/aW1hZ2VzLy4uL3NlY3JldA=="
    )
    assert resp.status == 400

    # Percent-encoded path traversal (e.g. images/%2e%2e/%2e%2e/api/admin) -> 400
    # b64 for "images/%2e%2e/%2e%2e/api/admin" is "aW1hZ2VzLyUyZSUyZS8lMmUlMmUvYXBpL2FkbWlu"
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/aW1hZ2VzLyUyZSUyZS8lMmUlMmUvYXBpL2FkbWlu"
    )
    assert resp.status == 400

    # Multiply encoded path traversal (e.g. images/%252e%252e/api/admin) -> 400
    # b64 for "images/%252e%252e/api/admin" is "aW1hZ2VzLyUyNTJlJTI1MmUvYXBpL2FkbWlu"
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/aW1hZ2VzLyUyNTJlJTI1MmUvYXBpL2FkbWlu"
    )
    assert resp.status == 400

    # Excessively multiply-encoded path that exceeds canonicalization iteration limit -> 400
    # b64 for "%252525252525252525252525" is "JTI1MjUyNTI1MjUyNTI1MjUyNTI1MjUyNQ=="
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/JTI1MjUyNTI1MjUyNTI1MjUyNTI1MjUyNQ=="
    )
    assert resp.status == 400

    # 4. Absolute path -> 400
    # b64 for "/etc/passwd" is "L2V0Yy9wYXNzd2Q="
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/L2V0Yy9wYXNzd2Q="
    )
    assert resp.status == 400

    # 5. Arbitrary relative path (SSRF prevention, e.g. "api/admin") -> 400
    # b64 for "api/admin" is "YXBpL2FkbWlu"
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/YXBpL2FkbWlu"
    )
    assert resp.status == 400

    # 6. Upstream connection failure / client error -> 502
    upstream_url = "https://127.0.0.1:443/indi-allsky/images/error.jpg"
    mock_indi_allsky_client.get_media_url.return_value = upstream_url
    aioclient_mock.get(upstream_url, exc=TimeoutError())

    # b64 for "images/error.jpg" is "aW1hZ2VzL2Vycm9yLmpwZw=="
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/aW1hZ2VzL2Vycm9yLmpwZw=="
    )
    assert resp.status == 502

    # 7. Upstream cross-origin redirect -> 502 (SSRF prevention)
    latest_url = "https://127.0.0.1:443/indi-allsky/latestimage"
    mock_indi_allsky_client.get_media_url.return_value = latest_url
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        latest_url,
        status=302,
        headers={"Location": "http://169.254.169.254/latest/meta-data"},
    )
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0aW1hZ2U="
    )
    assert resp.status == 502

    # 8. Upstream redirect without Location header -> 502
    aioclient_mock.clear_requests()
    aioclient_mock.get(latest_url, status=302)
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0aW1hZ2U="
    )
    assert resp.status == 502

    # Upstream redirect with malformed Location header -> 502
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        latest_url,
        status=302,
        headers={"Location": "http://[invalid-ipv6/path"},
    )
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0aW1hZ2U="
    )
    assert resp.status == 502

    # 9. Upstream redirect loop (>5 hops) -> 502
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        latest_url,
        status=302,
        headers={"Location": "/indi-allsky/latestimage"},
    )
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0aW1hZ2U="
    )
    assert resp.status == 502

    # 10. Valid same-origin redirect in proxy view succeeds
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        latest_url,
        status=302,
        headers={"Location": "/indi-allsky/images/resolved.jpg"},
    )
    aioclient_mock.get(
        "https://127.0.0.1:443/indi-allsky/images/resolved.jpg",
        status=200,
        content=b"resolved-data",
        headers={"Content-Type": "image/jpeg"},
    )
    resp = await client.get(
        f"/api/indi_allsky/media/{mock_config_entry.entry_id}/bGF0ZXN0aW1hZ2U="
    )
    assert resp.status == 200
    assert await resp.read() == b"resolved-data"

    # 11. Entry from another domain -> 404
    foreign_entry = MockConfigEntry(
        domain="other_domain",
        state=ConfigEntryState.LOADED,
    )
    foreign_entry.add_to_hass(hass)
    resp = await client.get(f"/api/indi_allsky/media/{foreign_entry.entry_id}/c2FtcGxl")
    assert resp.status == 404


async def test_proxy_view_streaming_error_mid_stream(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test proxy view handling when upstream errors after response is prepared."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    upstream_url = "https://127.0.0.1:443/indi-allsky/images/failing.jpg"
    mock_indi_allsky_client.get_media_url.return_value = upstream_url

    await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{mock_config_entry.entry_id}#media#images/failing.jpg",
        None,
    )

    client = await hass_client()

    class FailingStreamContent:
        async def iter_chunked(self, size: int) -> AsyncIterator[bytes]:
            yield b"initial_chunk"
            raise ClientError("Stream broken")

    @asynccontextmanager
    async def mock_get(*args, **kwargs):
        yield SimpleNamespace(
            status=200,
            headers={"Content-Type": "image/jpeg"},
            content=FailingStreamContent(),
        )

    upstream_url = "https://127.0.0.1:443/indi-allsky/images/failing.jpg"
    mock_indi_allsky_client.get_media_url.return_value = upstream_url

    with patch(
        "homeassistant.components.indi_allsky.media_source.async_get_clientsession"
    ) as mock_session_getter:
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=mock_get)
        mock_session_getter.return_value = mock_session

        # b64 for "images/failing.jpg" is "aW1hZ2VzL2ZhaWxpbmcuanBn"
        resp = await client.get(
            f"/api/indi_allsky/media/{mock_config_entry.entry_id}/aW1hZ2VzL2ZhaWxpbmcuanBn"
        )
        assert resp.status == 200
        assert await resp.content.readexactly(13) == b"initial_chunk"
        with pytest.raises(client_exceptions.ClientPayloadError):
            await resp.content.read()
