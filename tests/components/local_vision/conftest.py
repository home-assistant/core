"""Fixtures for the Local vision tests."""

from collections.abc import Generator
import io
import random
from unittest.mock import patch

from PIL import Image, ImageDraw
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.local_vision.const import DOMAIN
from homeassistant.components.media_source import MediaImage
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


def scene(*, car: bool, seed: int, grey: bool = False) -> bytes:
    """Return a JPEG of a garage bay, with or without a car."""
    rng = random.Random(seed)
    image = Image.new("RGB", (320, 240), (128, 128, 128))
    if not grey:
        draw = ImageDraw.Draw(image)
        for x in range(0, 320, 40):
            draw.line((x, 0, x, 240), fill=(90, 90, 90), width=3)
        draw.rectangle((0, 200, 320, 240), fill=(60, 60, 60))
        if car:
            shift = rng.randint(-8, 8)
            draw.rounded_rectangle(
                (90 + shift, 90, 230 + shift, 200), radius=20, fill=(20, 40, 160)
            )
            draw.rectangle((110 + shift, 100, 210 + shift, 140), fill=(200, 220, 240))
        for _ in range(200):
            x, y = rng.randrange(320), rng.randrange(240)
            draw.point((x, y), fill=(rng.randrange(256),) * 3)
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()


@pytest.fixture
def media() -> Generator[dict[str, bytes]]:
    """Serve JPEGs by media content ID; fill the mapping in the test."""
    images: dict[str, bytes] = {}

    async def get_image(hass: HomeAssistant, media_content_id: str) -> MediaImage:
        return MediaImage(mime_type="image/jpeg", content=images[media_content_id])

    with patch(
        "homeassistant.components.media_source.async_get_media_image",
        side_effect=get_image,
    ):
        yield images


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the config entry."""
    entry = MockConfigEntry(domain=DOMAIN, title="Local vision", entry_id="vision")
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the integration."""
    # Conversation, a dependency of AI Task, needs the core integration.
    assert await async_setup_component(hass, "homeassistant", {})
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Skip setting up the entry."""
    with patch(
        "homeassistant.components.local_vision.async_setup_entry", return_value=True
    ):
        yield
