"""Test the BraviaTV coordinator."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.braviatv.const import SourceType
from homeassistant.components.braviatv.coordinator import BraviaTVCoordinator
from homeassistant.core import HomeAssistant


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
