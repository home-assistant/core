"""Test the Immich sensor platform."""

from unittest.mock import Mock, patch

from aiohttp import ContentTypeError, RequestInfo
from multidict import CIMultiDict, CIMultiDictProxy
import pytest
from syrupy.assertion import SnapshotAssertion
from yarl import URL

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Immich sensor platform."""

    with patch("homeassistant.components.immich.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_admin_sensors(
    hass: HomeAssistant,
    mock_non_admin_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the integration doesn't create admin sensors if not admin."""

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.mock_title_photos_count") is None
    assert hass.states.get("sensor.mock_title_videos_count") is None
    assert hass.states.get("sensor.mock_title_disk_used_by_photos") is None
    assert hass.states.get("sensor.mock_title_disk_used_by_videos") is None


async def test_update_error_does_not_leak_api_key(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that API key is not leaked in error logs on connection failure."""
    await setup_integration(hass, mock_config_entry)

    api_key = "SECRET_API_KEY_12345"
    headers = CIMultiDictProxy(
        CIMultiDict({"x-api-key": api_key, "Host": "example.com"})
    )
    request_info = RequestInfo(
        url=URL("https://example.com/api/server/about"),
        method="GET",
        headers=headers,
        real_url=URL("https://example.com/api/server/about"),
    )
    mock_immich.server.async_get_about_info.side_effect = ContentTypeError(
        request_info, (), status=503, message="Service Unavailable"
    )

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert api_key not in caplog.text
