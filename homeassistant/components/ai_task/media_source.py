"""Expose images as media sources."""

import logging
from pathlib import Path
from time import time

from homeassistant.components.media_source import local_source
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.singleton import singleton

from .const import DATA_MEDIA_SOURCE, DOMAIN, IMAGE_DIR

_LOGGER = logging.getLogger(__name__)


@singleton(DATA_MEDIA_SOURCE, async_=True)
async def async_get_media_source(hass: HomeAssistant) -> local_source.LocalSource:
    """Set up local media source."""
    media_dirs = list(hass.config.media_dirs.values())

    if not media_dirs:
        raise HomeAssistantError(
            "AI Task media source requires at least one media directory configured"
        )

    media_dir = Path(media_dirs[0]) / DOMAIN / IMAGE_DIR

    return local_source.LocalSource(
        hass,
        DOMAIN,
        "AI generated images",
        {IMAGE_DIR: str(media_dir)},
        f"/{DOMAIN}",
    )


async def async_clear_images(hass: HomeAssistant, days: int | None) -> None:
    """Delete generated images, or only those older than the given days."""
    source = await async_get_media_source(hass)
    image_dir = Path(source.media_dirs[IMAGE_DIR])
    cutoff = None if days is None else time() - days * 86400

    def remove_images() -> None:
        """Remove images from the filesystem."""
        if not image_dir.is_dir():
            return
        for image in image_dir.iterdir():
            try:
                if not image.is_file() or (
                    cutoff is not None and image.stat().st_mtime >= cutoff
                ):
                    continue
                image.unlink()
            except OSError as err:
                _LOGGER.warning("Can't remove image '%s': %s", image.name, err)

    await hass.async_add_executor_job(remove_images)
