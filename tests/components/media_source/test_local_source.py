"""Test Local Media Source."""

from collections.abc import AsyncGenerator
from http import HTTPStatus
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from homeassistant.components import media_source, websocket_api
from homeassistant.components.media_player import (
    BrowseError,
    MediaClass,
    SearchMediaQuery,
)
from homeassistant.components.media_source import const
from homeassistant.components.media_source.local_source import MAX_SEARCH_RESULTS
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.setup import async_setup_component

from tests.common import MockUser
from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture
async def temp_dir(hass: HomeAssistant) -> AsyncGenerator[str]:
    """Return a temp dir."""
    with TemporaryDirectory() as tmpdirname:
        target_dir = Path(tmpdirname) / "another_subdir"
        target_dir.mkdir()
        await async_process_ha_core_config(
            hass, {"media_dirs": {"test_dir": str(target_dir)}}
        )
        assert await async_setup_component(hass, const.DOMAIN, {})

        yield str(target_dir)


async def test_async_browse_media(hass: HomeAssistant) -> None:
    """Test browse media."""
    local_media = hass.config.path("media")
    await async_process_ha_core_config(
        hass, {"media_dirs": {"local": local_media, "recordings": local_media}}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    # Test path not exists
    with pytest.raises(BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"{const.URI_SCHEME}{const.DOMAIN}/local/test/not/exist"
        )
    assert str(excinfo.value) == "Path does not exist."

    # Test browse file
    with pytest.raises(BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"{const.URI_SCHEME}{const.DOMAIN}/local/test.mp3"
        )
    assert str(excinfo.value) == "Path is not a directory."

    # Test invalid base
    with pytest.raises(BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"{const.URI_SCHEME}{const.DOMAIN}/invalid/base"
        )
    assert str(excinfo.value) == "Unknown source directory."

    # Test directory traversal
    with pytest.raises(BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"{const.URI_SCHEME}{const.DOMAIN}/local/../configuration.yaml"
        )
    assert str(excinfo.value) == "Invalid path."

    # Test successful listing
    media = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{const.DOMAIN}"
    )
    assert media

    media = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{const.DOMAIN}/local/."
    )
    assert media

    media = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{const.DOMAIN}/recordings/."
    )
    assert media


async def test_async_search_media(hass: HomeAssistant) -> None:
    """Test searching local media."""
    local_media = hass.config.path("media")
    await async_process_ha_core_config(
        hass, {"media_dirs": {"local": local_media, "recordings": local_media}}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    # Search within a single directory (contextual)
    result = await media_source.async_search_media(
        hass,
        f"{const.URI_SCHEME}{const.DOMAIN}/local",
        SearchMediaQuery(search_query="test"),
    )
    assert [item.title for item in result.result] == ["test.mp3"]
    assert (
        result.result[0].media_content_id
        == f"{const.URI_SCHEME}{const.DOMAIN}/local/test.mp3"
    )

    # Search across all directories (global) finds the file in both dirs
    result = await media_source.async_search_media(
        hass,
        f"{const.URI_SCHEME}{const.DOMAIN}",
        SearchMediaQuery(search_query="sax"),
    )
    assert {item.title for item in result.result} == {"Epic Sax Guy 10 Hours.mp4"}
    assert len(result.result) == 2

    # Non-media files are not returned
    result = await media_source.async_search_media(
        hass,
        f"{const.URI_SCHEME}{const.DOMAIN}/local",
        SearchMediaQuery(search_query="not_media"),
    )
    assert result.result == []

    # Searching a non-existent directory returns no results
    result = await media_source.async_search_media(
        hass,
        f"{const.URI_SCHEME}{const.DOMAIN}/local/nonexistent",
        SearchMediaQuery(search_query="test"),
    )
    assert result.result == []

    # Filter by media class
    result = await media_source.async_search_media(
        hass,
        f"{const.URI_SCHEME}{const.DOMAIN}/local",
        SearchMediaQuery(search_query="", media_filter_classes=[MediaClass.MUSIC]),
    )
    assert [item.title for item in result.result] == ["test.mp3"]

    # Invalid path raises a BrowseError
    with pytest.raises(BrowseError):
        await media_source.async_search_media(
            hass,
            f"{const.URI_SCHEME}{const.DOMAIN}/local/../secret",
            SearchMediaQuery(search_query="test"),
        )


async def test_async_search_media_limit_and_hidden(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test that search caps results and skips hidden files."""
    for i in range(MAX_SEARCH_RESULTS + 20):
        (tmp_path / f"song_{i}.mp3").touch()
    (tmp_path / ".hidden_song.mp3").touch()

    await async_process_ha_core_config(
        hass, {"media_dirs": {"local": str(tmp_path), "recordings": str(tmp_path)}}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    # Global search across both dirs; the first dir already fills the limit
    result = await media_source.async_search_media(
        hass,
        f"{const.URI_SCHEME}{const.DOMAIN}",
        SearchMediaQuery(search_query="song"),
    )
    assert len(result.result) == MAX_SEARCH_RESULTS
    assert all(not item.title.startswith(".") for item in result.result)


async def test_browse_media_can_search(hass: HomeAssistant) -> None:
    """Test that browsable directories advertise search support."""
    local_media = hass.config.path("media")
    await async_process_ha_core_config(
        hass, {"media_dirs": {"local": local_media, "recordings": local_media}}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    # The root of multiple directories is searchable
    media = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{const.DOMAIN}"
    )
    assert media.can_search

    # A directory is searchable, but the files inside it are not
    media = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{const.DOMAIN}/local/."
    )
    assert media.can_search
    file_child = next(child for child in media.children if child.can_play)
    assert not file_child.can_search


async def test_media_view(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test media view."""
    local_media = hass.config.path("media")
    await async_process_ha_core_config(
        hass, {"media_dirs": {"local": local_media, "recordings": local_media}}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(hass, const.DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_client()

    # Protects against non-existent files
    resp = await client.head("/media/local/invalid.txt")
    assert resp.status == HTTPStatus.NOT_FOUND

    resp = await client.get("/media/local/invalid.txt")
    assert resp.status == HTTPStatus.NOT_FOUND

    resp = await client.get("/media/recordings/invalid.txt")
    assert resp.status == HTTPStatus.NOT_FOUND

    # Protects against non-media files
    resp = await client.head("/media/local/not_media.txt")
    assert resp.status == HTTPStatus.NOT_FOUND

    resp = await client.get("/media/local/not_media.txt")
    assert resp.status == HTTPStatus.NOT_FOUND

    # Protects against unknown local media sources
    resp = await client.head("/media/unknown_source/not_media.txt")
    assert resp.status == HTTPStatus.NOT_FOUND

    resp = await client.get("/media/unknown_source/not_media.txt")
    assert resp.status == HTTPStatus.NOT_FOUND

    # Fetch available media
    resp = await client.head("/media/local/test.mp3")
    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "audio/mpeg"

    resp = await client.get("/media/local/test.mp3")
    assert resp.status == HTTPStatus.OK

    resp = await client.head("/media/local/Epic Sax Guy 10 Hours.mp4")
    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "video/mp4"

    resp = await client.get("/media/local/Epic Sax Guy 10 Hours.mp4")
    assert resp.status == HTTPStatus.OK

    resp = await client.get("/media/recordings/test.mp3")
    assert resp.status == HTTPStatus.OK


async def test_upload_view(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    temp_dir: str,
    tmp_path: Path,
    hass_admin_user: MockUser,
) -> None:
    """Allow uploading media."""
    # We need a temp dir that's not under tempdir fixture
    extra_media_dir = tmp_path
    hass.config.media_dirs["another_path"] = temp_dir

    img = (Path(__file__).parent.parent / "image_upload/logo.png").read_bytes()

    def get_file(name):
        pic = io.BytesIO(img)
        pic.name = name
        return pic

    client = await hass_client()

    # Test normal upload
    with patch.object(Path, "mkdir", autospec=True, return_value=None) as mock_mkdir:
        res = await client.post(
            "/api/media_source/local_source/upload",
            data={
                "media_content_id": "media-source://media_source/test_dir",
                "file": get_file("logo.png"),
            },
        )

    assert res.status == 200
    data = await res.json()
    assert data["media_content_id"] == "media-source://media_source/test_dir/logo.png"
    uploaded_path = Path(temp_dir) / "logo.png"
    assert uploaded_path.is_file()
    mock_mkdir.assert_called_once()

    resolved = await media_source.async_resolve_media(
        hass, data["media_content_id"], target_media_player=None
    )
    assert resolved.url == "/media/test_dir/logo.png"
    assert resolved.mime_type == "image/png"
    assert resolved.path == uploaded_path

    # Test with bad media source ID
    for bad_id in (
        # Main dir doesn't exist
        "media-source://media_source/test_dir2",
        # Location is invalid
        "media-source://media_source/test_dir/..",
        # Domain != media_source
        "media-source://nest/test_dir/.",
        # Other directory
        f"media-source://media_source/another_path///{extra_media_dir}/",
        # Completely something else
        "http://bla",
    ):
        res = await client.post(
            "/api/media_source/local_source/upload",
            data={
                "media_content_id": bad_id,
                "file": get_file("bad-source-id.png"),
            },
        )

        assert res.status == 400, bad_id
        assert not (Path(temp_dir) / "bad-source-id.png").is_file()

    # Test invalid POST data
    res = await client.post(
        "/api/media_source/local_source/upload",
        data={
            "media_content_id": "media-source://media_source/test_dir/.",
            "file": get_file("invalid-data.png"),
            "incorrect": "format",
        },
    )

    assert res.status == 400
    assert not (Path(temp_dir) / "invalid-data.png").is_file()

    # Test invalid content type
    text_file = io.BytesIO(b"Hello world")
    text_file.name = "hello.txt"
    res = await client.post(
        "/api/media_source/local_source/upload",
        data={
            "media_content_id": "media-source://media_source/test_dir/.",
            "file": text_file,
        },
    )

    assert res.status == 400
    assert not (Path(temp_dir) / "hello.txt").is_file()

    # Test invalid filename
    with patch(
        "aiohttp.formdata.guess_filename", return_value="../invalid-filename.png"
    ):
        res = await client.post(
            "/api/media_source/local_source/upload",
            data={
                "media_content_id": "media-source://media_source/test_dir/.",
                "file": get_file("../invalid-filename.png"),
            },
        )

    assert res.status == 400
    assert not (Path(temp_dir) / "../invalid-filename.png").is_file()

    # Remove admin access
    hass_admin_user.groups = []
    res = await client.post(
        "/api/media_source/local_source/upload",
        data={
            "media_content_id": "media-source://media_source/test_dir/.",
            "file": get_file("no-admin-test.png"),
        },
    )

    assert res.status == 401
    assert not (Path(temp_dir) / "no-admin-test.png").is_file()


async def test_remove_file(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    temp_dir: str,
    hass_admin_user: MockUser,
) -> None:
    """Allow uploading media."""

    msg_count = 0
    file_count = 0

    def msgid():
        nonlocal msg_count
        msg_count += 1
        return msg_count

    def create_file():
        nonlocal file_count
        file_count += 1
        to_delete_path = Path(temp_dir) / f"to_delete_{file_count}.txt"
        to_delete_path.touch()
        return to_delete_path

    client = await hass_ws_client(hass)
    to_delete = create_file()

    await client.send_json(
        {
            "id": msgid(),
            "type": "media_source/local_source/remove",
            "media_content_id": f"media-source://media_source/test_dir/{to_delete.name}",
        }
    )

    msg = await client.receive_json()

    assert msg["success"]

    assert not to_delete.exists()

    # Test with bad media source ID
    extra_id_file = create_file()
    for bad_id, err in (
        # Not exists
        (
            "media-source://media_source/test_dir/not_exist.txt",
            websocket_api.ERR_NOT_FOUND,
        ),
        # Only a dir
        ("media-source://media_source/test_dir", websocket_api.ERR_NOT_SUPPORTED),
        # File with extra identifiers
        (
            f"media-source://media_source/test_dir/bla/../{extra_id_file.name}",
            websocket_api.ERR_INVALID_FORMAT,
        ),
        # Location is invalid
        ("media-source://media_source/test_dir/..", websocket_api.ERR_INVALID_FORMAT),
        # Domain != media_source
        ("media-source://nest/test_dir/.", websocket_api.ERR_INVALID_FORMAT),
        # Completely something else
        ("http://bla", websocket_api.ERR_INVALID_FORMAT),
    ):
        await client.send_json(
            {
                "id": msgid(),
                "type": "media_source/local_source/remove",
                "media_content_id": bad_id,
            }
        )

        msg = await client.receive_json()

        assert not msg["success"], bad_id
        assert msg["error"]["code"] == err

    assert extra_id_file.exists()

    # Test error deleting
    to_delete_2 = create_file()

    with patch("pathlib.Path.unlink", side_effect=OSError):
        await client.send_json(
            {
                "id": msgid(),
                "type": "media_source/local_source/remove",
                "media_content_id": f"media-source://media_source/test_dir/{to_delete_2.name}",
            }
        )

        msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == websocket_api.ERR_UNKNOWN_ERROR

    # Test requires admin access
    to_delete_3 = create_file()
    hass_admin_user.groups = []

    await client.send_json(
        {
            "id": msgid(),
            "type": "media_source/local_source/remove",
            "media_content_id": f"media-source://media_source/test_dir/{to_delete_3.name}",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert to_delete_3.is_file()
