"""Test the Foscam component."""

from unittest.mock import MagicMock, patch

from homeassistant.components.foscam import async_migrate_entry
from homeassistant.components.foscam.const import CONF_RTSP_PORT
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_async_migrate_entry_gets_rtsp_port(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that async_migrate_entry correctly fetches and stores the RTSP port."""
    # 创建一个 version=1 的 entry
    entry = MockConfigEntry(
        domain="foscam",
        data={
            CONF_HOST: "192.168.1.123",
            CONF_PORT: 88,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
        entry_id="test_entry_id",
        version=1,
    )
    entry.add_to_hass(hass)

    mock_camera = MagicMock()
    mock_camera.get_port_info.return_value = (0, {"rtspPort": 554})

    with patch(
        "homeassistant.components.foscam.FoscamCamera", return_value=mock_camera
    ):
        assert await async_migrate_entry(hass, entry)

    assert entry.data[CONF_RTSP_PORT] == 554
    assert entry.version == 2
