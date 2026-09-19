"""Fixtures for Immich Frames tests."""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

from PIL import Image
import pytest

from homeassistant.components.immich.const import DOMAIN as IMMICH_DOMAIN
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
from tests.components.immich.const import ALBUM_DATA, MOCK_SEARCH_ASSETS


@pytest.fixture
def mock_immich_api() -> SimpleNamespace:
    """Return a mocked API exposed by the parent Immich integration."""
    image = BytesIO()
    Image.new("RGB", (4, 3), "red").save(image, "JPEG")
    return SimpleNamespace(
        search=SimpleNamespace(
            async_get_all=AsyncMock(return_value=MOCK_SEARCH_ASSETS),
            async_get_all_by_album_ids=AsyncMock(return_value=MOCK_SEARCH_ASSETS),
            async_smart_search=AsyncMock(return_value=MOCK_SEARCH_ASSETS),
        ),
        albums=SimpleNamespace(
            async_get_all_albums=AsyncMock(return_value=[ALBUM_DATA])
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


@pytest.fixture
def ignore_missing_translations(request: pytest.FixtureRequest) -> list[str]:
    """Ignore an unrelated missing translation in the current Core checkout."""
    translations: list[str] = []
    if request.node.name in {
        "test_user_requires_immich",
        "test_user_creates_frame",
        "test_user_aborts_when_immich_is_not_loaded",
        "test_setup_entry_creates_image",
        "test_diagnostics_exclude_image_bytes",
        "test_user_creates_album_frame",
        "test_user_creates_smart_frame",
        "test_options_flow_updates_display_settings",
        "test_reconfigure_flow_updates_frame_name",
        "test_options_flow_configures_album_source",
        "test_options_flow_configures_smart_source",
        "test_user_validation_errors",
        "test_album_flow_validates_empty_and_unknown_albums",
        "test_album_flow_aborts_when_no_albums",
        "test_smart_flow_requires_a_query",
    }:
        translations.append("component.immich.")
    if request.node.name == "test_reconfigure_flow_updates_frame_name":
        translations.append("component.homeassistant.")
    if request.node.name in {
        "test_user_creates_frame",
        "test_setup_entry_creates_image",
        "test_diagnostics_exclude_image_bytes",
        "test_user_creates_album_frame",
        "test_user_creates_smart_frame",
    }:
        translations.append("component.image.")
        translations.append("component.button.")
        translations.append("component.switch.")
    return translations
