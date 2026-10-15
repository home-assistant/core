"""Tests for the Collection Image diagnostics."""

from pathlib import Path

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.collection_image.const import DOMAIN
from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.components.media_source import PlayMedia, Unresolvable
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MediaSourceState
from .const import (
    MOCK_MEDIA_DIR_URI_1,
    MOCK_MEDIA_DIR_URI_BROWSE_ERROR,
    MOCK_MEDIA_DIR_URI_EMPTY,
    MOCK_MEDIA_IMAGE_URI_1,
)
from .helpers import config_entry_from_uri

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("mock_media_source")
@pytest.mark.parametrize(
    ("uris", "play_media"),
    [
        pytest.param(
            [
                MOCK_MEDIA_DIR_URI_1,
                MOCK_MEDIA_DIR_URI_EMPTY,
                MOCK_MEDIA_DIR_URI_BROWSE_ERROR,
            ],
            PlayMedia(url="", mime_type="image/png", path=Path("/media/photo.png")),
            id="path",
        ),
        pytest.param(
            [MOCK_MEDIA_DIR_URI_1],
            PlayMedia(
                url="https://example.com/photo.png?token=secret",
                mime_type="image/png",
            ),
            id="url",
        ),
        pytest.param(
            [MOCK_MEDIA_DIR_URI_EMPTY],
            PlayMedia(url="", mime_type="image/png", path=Path("/media/photo.png")),
            id="unavailable",
        ),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    media_source_state: MediaSourceState,
    uris: list[str],
    play_media: PlayMedia,
) -> None:
    """Test config entry diagnostics."""
    media_source_state.resolve_results[MOCK_MEDIA_IMAGE_URI_1] = play_media
    config_entry = config_entry_from_uri(uris)
    config_entry.add_to_hass(hass)
    with freeze_time("2025-11-08T12:00:00+00:00"):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )


@pytest.mark.usefixtures("mock_media_source")
async def test_diagnostics_entity_disabled(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test diagnostics when the image entity has no state."""
    config_entry = config_entry_from_uri(MOCK_MEDIA_DIR_URI_1)
    config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        IMAGE_DOMAIN,
        DOMAIN,
        config_entry.entry_id,
        config_entry=config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics["current_image"] is None


@pytest.mark.usefixtures("mock_media_source")
async def test_diagnostics_unresolvable(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    media_source_state: MediaSourceState,
) -> None:
    """Test diagnostics when the current image can no longer be resolved."""
    config_entry = config_entry_from_uri(MOCK_MEDIA_DIR_URI_1)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    media_source_state.resolve_exceptions[MOCK_MEDIA_IMAGE_URI_1] = Unresolvable(
        "Image was deleted"
    )

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics["current_image"]["resolved"] == {"error": "Image was deleted"}
