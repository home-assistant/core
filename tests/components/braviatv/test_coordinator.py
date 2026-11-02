"""Test the BraviaTV coordinator."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.braviatv.const import SourceType
from homeassistant.components.braviatv.coordinator import BraviaTVCoordinator
from homeassistant.components.media_player import MediaType
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError


@pytest.mark.parametrize(
    "start_datetime",
    [
        "2026-08-22T12:00:00",  # naive, treated as local time (CEST UTC+2)
        "2026-08-22T12:00:00+02:00",  # aware
    ],
)
@pytest.mark.freeze_time("2026-08-22T12:00:00+00:00")
async def test_async_update_playing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
    start_datetime: str,
) -> None:
    """Test updating playing info with a start datetime."""
    await hass.config.async_set_time_zone("Europe/Warsaw")
    mock_braviatv_client.get_playing_info.return_value = {
        "startDateTime": start_datetime
    }
    coordinator = BraviaTVCoordinator(hass, mock_config_entry, mock_braviatv_client)

    await coordinator.async_update_playing()

    assert coordinator.media_position == 7200
    assert coordinator.media_position_updated_at == datetime(
        2026, 8, 22, 12, 0, 0, tzinfo=UTC
    )


async def test_async_update_sources_skips_incomplete_items(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test sources without a title or URI are ignored."""
    mock_braviatv_client.get_external_status.return_value = [
        {"uri": "extInput:hdmi?port=1", "title": "HDMI 1"},
        {"uri": "extInput:hdmi?port=2", "title": ""},
        {"title": "AV/Component"},
    ]
    mock_braviatv_client.get_app_list.return_value = []
    mock_braviatv_client.get_content_list_all.return_value = []
    coordinator = BraviaTVCoordinator(hass, mock_config_entry, mock_braviatv_client)

    await coordinator.async_update_sources()

    assert coordinator.source_list == ["HDMI 1"]
    assert coordinator.source_map == {
        "extInput:hdmi?port=1": {
            "uri": "extInput:hdmi?port=1",
            "title": "HDMI 1",
            "type": SourceType.INPUT,
        }
    }


async def test_async_source_find_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test finding a source that does not exist raises a validation error."""
    coordinator = BraviaTVCoordinator(hass, mock_config_entry, mock_braviatv_client)
    coordinator.source_map = {
        "extInput:hdmi?port=1": {
            "uri": "extInput:hdmi?port=1",
            "title": "HDMI 1",
            "type": SourceType.INPUT,
        }
    }

    with pytest.raises(ServiceValidationError) as exc_info:
        await coordinator.async_source_find("HDMI 9", SourceType.INPUT)

    assert exc_info.value.translation_key == "source_not_found"
    assert exc_info.value.translation_placeholders == {
        "device": "BRAVIA TV-Model",
        "source_type": "input",
        "query": "HDMI 9",
    }
    mock_braviatv_client.set_play_content.assert_not_called()


async def test_async_play_media_invalid_media_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test playing an unsupported media type raises a validation error."""
    coordinator = BraviaTVCoordinator(hass, mock_config_entry, mock_braviatv_client)

    with pytest.raises(ServiceValidationError) as exc_info:
        await coordinator.async_play_media(MediaType.MUSIC, "something")

    assert exc_info.value.translation_key == "invalid_media_type"
    assert exc_info.value.translation_placeholders == {
        "device": "BRAVIA TV-Model",
        "media_type": "music",
    }


async def test_async_send_command_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test sending an unsupported command raises a validation error."""
    mock_braviatv_client.send_command.return_value = False
    coordinator = BraviaTVCoordinator(hass, mock_config_entry, mock_braviatv_client)

    with pytest.raises(ServiceValidationError) as exc_info:
        await coordinator.async_send_command(["Foo", "Bar"], 2)

    assert exc_info.value.translation_key == "unsupported_command"
    assert exc_info.value.translation_placeholders == {
        "device": "BRAVIA TV-Model",
        "command": "Foo",
    }
    mock_braviatv_client.send_command.assert_called_once_with("Foo")
