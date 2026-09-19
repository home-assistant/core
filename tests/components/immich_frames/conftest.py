"""Fixtures for Immich Frames tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

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
from tests.components.immich.const import MOCK_SEARCH_ASSETS


@pytest.fixture
def mock_immich_api() -> SimpleNamespace:
    """Return a mocked API exposed by the parent Immich integration."""
    return SimpleNamespace(
        search=SimpleNamespace(
            async_get_all=AsyncMock(return_value=MOCK_SEARCH_ASSETS)
        ),
        assets=SimpleNamespace(async_view_asset=AsyncMock(return_value=b"jpeg-bytes")),
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
    translations = ["component.immich."]
    if request.node.name in {
        "test_user_creates_frame",
        "test_setup_entry_creates_image",
        "test_diagnostics_exclude_image_bytes",
    }:
        translations.append("component.image.")
    return translations
