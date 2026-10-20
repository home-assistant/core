"""Tests for the taught frames as media sources."""

from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components import media_source
from homeassistant.components.image_classification.const import DOMAIN
from homeassistant.components.media_player import BrowseError
from homeassistant.core import HomeAssistant

from . import TEST_DOMAIN, FakeCamera, setup_integration, stored_frames, teach


@pytest.fixture
async def frame_id(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    camera: FakeCamera,
) -> str:
    """Return the id of a frame taught to the set up entry."""
    await setup_integration(hass, mock_config_entry)
    await teach(hass, mock_config_entry, "on")
    return stored_frames(hass_storage, mock_config_entry)[0]["id"]


async def test_resolve(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    frame_id: str,
) -> None:
    """A taught frame resolves to its file."""
    media = await media_source.async_resolve_media(
        hass,
        f"media-source://{DOMAIN}/{mock_config_entry.entry_id}/{frame_id}.jpg",
        None,
    )

    assert media.url == f"/api/{DOMAIN}/frame/{mock_config_entry.entry_id}/{frame_id}"
    assert media.mime_type == "image/jpeg"
    assert media.path == (
        config_dir / DOMAIN / mock_config_entry.entry_id / f"{frame_id}.jpg"
    )


@pytest.mark.parametrize(
    "identifier",
    [
        pytest.param("{entry_id}/{frame_id}", id="no_extension"),
        pytest.param("{entry_id}/../{frame_id}.jpg", id="nested"),
        pytest.param("{entry_id}/stray.jpg", id="frame_id"),
        pytest.param("{entry_id}/{unknown}.jpg", id="unknown_frame"),
        pytest.param("01JUNKNOWN/{frame_id}.jpg", id="unknown_entry"),
        pytest.param("{other_entry_id}/{frame_id}.jpg", id="other_domain"),
    ],
)
async def test_resolve_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    frame_id: str,
    identifier: str,
) -> None:
    """Anything but a taught frame of an entry is unresolvable."""
    other = MockConfigEntry(domain=TEST_DOMAIN)
    other.add_to_hass(hass)
    media_content_id = f"media-source://{DOMAIN}/" + identifier.format(
        entry_id=mock_config_entry.entry_id,
        other_entry_id=other.entry_id,
        frame_id=frame_id,
        unknown="0" * 32,
    )

    with pytest.raises(media_source.Unresolvable):
        await media_source.async_resolve_media(hass, media_content_id, None)


@pytest.mark.usefixtures("frame_id")
async def test_browse(hass: HomeAssistant) -> None:
    """Taught frames are managed in the options, there is nothing to browse."""
    root = await media_source.async_browse_media(hass, f"media-source://{DOMAIN}")
    assert root.title == "Image classification"
    assert root.children == []

    with pytest.raises(BrowseError):
        await media_source.async_browse_media(hass, f"media-source://{DOMAIN}/frames")


async def test_frame_served_to_admins(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    frame_id: str,
) -> None:
    """Administrators can open taught frames, others can't."""
    client = await hass_client()
    url = f"/api/{DOMAIN}/frame/{mock_config_entry.entry_id}/{frame_id}"
    path = config_dir / DOMAIN / mock_config_entry.entry_id / f"{frame_id}.jpg"

    response = await client.get(url)
    assert response.status == HTTPStatus.OK
    assert response.content_type == "image/jpeg"
    assert await response.read() == path.read_bytes()

    assert (
        await client.get(f"/api/{DOMAIN}/frame/{mock_config_entry.entry_id}/stray")
    ).status == HTTPStatus.NOT_FOUND

    hass_admin_user.groups = []
    assert (await client.get(url)).status == HTTPStatus.UNAUTHORIZED
