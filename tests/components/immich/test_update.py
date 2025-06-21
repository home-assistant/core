"""Test the Immich update platform."""

from unittest.mock import Mock, patch

from aioimmich.server.models import ImmichServerAbout
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Immich update platform."""

    with patch("homeassistant.components.immich.PLATFORMS", [Platform.UPDATE]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_min_version(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Immich update platform with min version not installed."""

    mock_immich.server.async_get_about_info.return_value = ImmichServerAbout.from_dict(
        {
            "version": "v1.132.3",
            "versionUrl": "https://github.com/immich-app/immich/releases/tag/v1.132.3",
            "licensed": False,
            "build": "14709928600",
            "buildUrl": "https://github.com/immich-app/immich/actions/runs/14709928600",
            "buildImage": "v1.132.3",
            "buildImageUrl": "https://github.com/immich-app/immich/pkgs/container/immich-server",
            "repository": "immich-app/immich",
            "repositoryUrl": "https://github.com/immich-app/immich",
            "sourceRef": "v1.132.3",
            "sourceCommit": "02994883fe3f3972323bb6759d0170a4062f5236",
            "sourceUrl": "https://github.com/immich-app/immich/commit/02994883fe3f3972323bb6759d0170a4062f5236",
            "nodejs": "v22.14.0",
            "exiftool": "13.00",
            "ffmpeg": "7.0.2-7",
            "libvips": "8.16.1",
            "imagemagick": "7.1.1-47",
        }
    )

    with patch("homeassistant.components.immich.PLATFORMS", [Platform.UPDATE]):
        await setup_integration(hass, mock_config_entry)

    assert not hass.states.async_all()
