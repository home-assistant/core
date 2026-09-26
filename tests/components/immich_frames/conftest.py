"""Fixtures for Immich Frames tests."""

from collections.abc import AsyncIterator
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from PIL import Image
import pytest

from homeassistant.components.immich import DOMAIN as IMMICH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.immich import const as immich_const


@pytest.fixture(autouse=True)
async def clean_frame_caches(hass: HomeAssistant) -> AsyncIterator[None]:
    """Remove frame cache files created by each test."""
    yield
    storage_path = Path(hass.config.path(".storage"))
    for cache_path in storage_path.glob("immich_frames_*.json"):
        await hass.async_add_executor_job(cache_path.unlink, True)


@pytest.fixture
def mock_immich_api() -> SimpleNamespace:
    """Return a mocked API exposed by the parent Immich integration."""
    image = BytesIO()
    Image.new("RGB", (4, 3), "red").save(image, "JPEG")
    return SimpleNamespace(
        search=SimpleNamespace(
            async_get_all=AsyncMock(return_value=immich_const.MOCK_SEARCH_ASSETS),
            async_get_all_by_album_ids=AsyncMock(
                return_value=immich_const.MOCK_SEARCH_ASSETS
            ),
            async_smart_search=AsyncMock(return_value=immich_const.MOCK_SEARCH_ASSETS),
        ),
        albums=SimpleNamespace(
            async_get_all_albums=AsyncMock(return_value=[immich_const.ALBUM_DATA])
        ),
        assets=SimpleNamespace(
            async_view_asset=AsyncMock(return_value=image.getvalue())
        ),
    )


@pytest.fixture
def parent_immich_entry(
    hass: HomeAssistant, mock_immich_api: SimpleNamespace
) -> MockConfigEntry:
    """Add a loaded parent Immich entry with runtime data."""
    entry = MockConfigEntry(
        domain=IMMICH_DOMAIN,
        title="Immich server",
        data={
            CONF_API_KEY: "test-key",
            CONF_HOST: "immich.local",
            CONF_PORT: 2283,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
        },
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)
    entry.runtime_data = SimpleNamespace(
        api=mock_immich_api,
        configuration_url="http://immich.local:2283",
    )
    return entry
