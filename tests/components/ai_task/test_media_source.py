"""Test ai_task media source."""

import os
from pathlib import Path
import time
from unittest.mock import patch

import pytest

from homeassistant.components import media_source
from homeassistant.components.ai_task.const import DATA_MEDIA_SOURCE, DOMAIN
from homeassistant.components.ai_task.media_source import async_get_media_source
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, Unauthorized

from tests.common import MockUser


async def test_local_media_source(hass: HomeAssistant, init_components: None) -> None:
    """Test that the image media source is created."""
    item = await media_source.async_browse_media(hass, "media-source://")

    assert any(c.title == "AI generated images" for c in item.children)

    source = await async_get_media_source(hass)
    assert isinstance(source, media_source.local_source.LocalSource)
    assert source.name == "AI generated images"
    assert source.domain == "ai_task"
    assert list(source.media_dirs) == ["image"]
    # Depending on Docker, the default is one of the two paths
    assert source.media_dirs["image"] in (
        "/media/ai_task/image",
        hass.config.path("media/ai_task/image"),
    )
    assert source.url_prefix == "/ai_task"


async def test_media_source_no_media_dirs(hass: HomeAssistant) -> None:
    """Test an error is raised when no media directories are configured."""
    hass.config.media_dirs = {}

    with pytest.raises(
        HomeAssistantError,
        match="AI Task media source requires at least one media directory configured",
    ):
        await async_get_media_source(hass)


OLD_IMAGE = "2025-06-14_225900_old.png"
RECENT_IMAGE = "2025-07-14_225900_recent.png"


def _write_image(path: Path, days_old: int) -> None:
    """Write an image that was generated days_old days ago."""
    path.write_bytes(b"png")
    created = time.time() - days_old * 86400
    os.utime(path, (created, created))


@pytest.fixture
async def image_dir(hass: HomeAssistant, init_components: None, tmp_path: Path) -> Path:
    """Point the AI generated images at a temporary directory."""
    await hass.async_add_executor_job(_write_image, tmp_path / OLD_IMAGE, 31)
    await hass.async_add_executor_job(_write_image, tmp_path / RECENT_IMAGE, 29)
    hass.data[DATA_MEDIA_SOURCE].media_dirs["image"] = str(tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    ("service_data", "expected_images"),
    [
        pytest.param({}, [], id="all"),
        pytest.param({"days": 30}, [RECENT_IMAGE], id="older_than_days"),
    ],
)
async def test_clear_images(
    hass: HomeAssistant,
    image_dir: Path,
    service_data: dict[str, int],
    expected_images: list[str],
) -> None:
    """Test clearing AI generated images."""
    await hass.services.async_call(DOMAIN, "clear_images", service_data, blocking=True)

    images = await hass.async_add_executor_job(os.listdir, image_dir)
    assert images == expected_images


async def test_clear_images_no_directory(
    hass: HomeAssistant, init_components: None, tmp_path: Path
) -> None:
    """Test clearing images before any image was generated."""
    hass.data[DATA_MEDIA_SOURCE].media_dirs["image"] = str(tmp_path / "missing")

    await hass.services.async_call(DOMAIN, "clear_images", {}, blocking=True)

    assert not (tmp_path / "missing").exists()


async def test_clear_images_remove_error(
    hass: HomeAssistant, image_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test images that can't be removed are logged and kept."""
    with patch.object(Path, "unlink", side_effect=OSError("No access")):
        await hass.services.async_call(DOMAIN, "clear_images", {}, blocking=True)

    images = await hass.async_add_executor_job(os.listdir, image_dir)
    assert sorted(images) == [OLD_IMAGE, RECENT_IMAGE]
    assert f"Can't remove image '{OLD_IMAGE}': No access" in caplog.text


async def test_clear_images_requires_admin(
    hass: HomeAssistant, image_dir: Path, hass_read_only_user: MockUser
) -> None:
    """Test only admins can clear images."""
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "clear_images",
            {},
            context=Context(user_id=hass_read_only_user.id),
            blocking=True,
        )

    images = await hass.async_add_executor_job(os.listdir, image_dir)
    assert sorted(images) == [OLD_IMAGE, RECENT_IMAGE]
