from __future__ import annotations

import io
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from PIL import Image
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from homeassistant.components.roborock.const import CONF_MAP_ROTATION
from homeassistant.components.roborock.image import RoborockMap


def _png_bytes(width: int, height: int) -> bytes:
    img = Image.new("RGB", (width, height))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _coordinator(hass: HomeAssistant):
    """Minimal coordinator-like object for RoborockCoordinatedEntityV1."""
    coord = SimpleNamespace()
    coord.hass = hass
    coord.duid_slug = "test_duid"
    coord.last_home_update = datetime.utcnow()

    # CoordinatorEntity expects async_add_listener to exist
    coord.async_add_listener = lambda _cb: (lambda: None)

    return coord


@pytest.mark.asyncio
async def test_roborock_map_rotation_90(hass: HomeAssistant) -> None:
    raw = _png_bytes(10, 20)

    config_entry = MagicMock()
    config_entry.options = {CONF_MAP_ROTATION: 90}

    home_trait = MagicMock()
    home_trait.home_map_content = {1: SimpleNamespace(image_content=raw)}

    entity = RoborockMap(
        config_entry=config_entry,
        coordinator=_coordinator(hass),
        home_trait=home_trait,
        map_flag=1,
        map_name="Test Map",
    )

    rotated = await entity.async_image()
    assert rotated is not None
    assert rotated != raw

    img = Image.open(io.BytesIO(rotated))
    assert img.size == (20, 10)


@pytest.mark.asyncio
async def test_roborock_map_rotation_0_returns_raw(hass: HomeAssistant) -> None:
    raw = _png_bytes(12, 34)

    config_entry = MagicMock()
    config_entry.options = {CONF_MAP_ROTATION: 0}

    home_trait = MagicMock()
    home_trait.home_map_content = {1: SimpleNamespace(image_content=raw)}

    entity = RoborockMap(
        config_entry=config_entry,
        coordinator=_coordinator(hass),
        home_trait=home_trait,
        map_flag=1,
        map_name="Test Map",
    )

    out = await entity.async_image()
    assert out == raw


@pytest.mark.asyncio
async def test_roborock_map_cache_invalidation_on_map_change(hass: HomeAssistant) -> None:
    raw1 = _png_bytes(10, 20)
    raw2 = _png_bytes(30, 40)

    config_entry = MagicMock()
    config_entry.options = {CONF_MAP_ROTATION: 90}

    home_trait = MagicMock()
    home_trait.home_map_content = {1: SimpleNamespace(image_content=raw1)}

    coord = _coordinator(hass)

    entity = RoborockMap(
        config_entry=config_entry,
        coordinator=coord,
        home_trait=home_trait,
        map_flag=1,
        map_name="Test Map",
    )

    rotated1 = await entity.async_image()
    img1 = Image.open(io.BytesIO(rotated1))
    assert img1.size == (20, 10)

    # Update map content and simulate coordinator update
    home_trait.home_map_content[1].image_content = raw2
    entity._handle_coordinator_update()

    rotated2 = await entity.async_image()
    img2 = Image.open(io.BytesIO(rotated2))
    assert img2.size == (40, 30)


@pytest.mark.asyncio
async def test_roborock_map_missing_flag_raises(hass: HomeAssistant) -> None:
    config_entry = MagicMock()
    config_entry.options = {CONF_MAP_ROTATION: 90}

    home_trait = MagicMock()
    home_trait.home_map_content = {}  # no map_flag present

    entity = RoborockMap(
        config_entry=config_entry,
        coordinator=_coordinator(hass),
        home_trait=home_trait,
        map_flag=1,
        map_name="Test Map",
    )

    with pytest.raises(HomeAssistantError):
        await entity.async_image()
