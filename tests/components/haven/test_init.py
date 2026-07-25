"""Test setup for the HAVEN IAQ integration."""

from unittest.mock import AsyncMock, patch

from haveniaq import DeviceInfo, SensorData

from homeassistant.components.haven.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import TEST_HOST, TEST_INFO, TEST_SENSORS

from tests.common import MockConfigEntry


async def test_setup_unload_ram_entry(hass: HomeAssistant) -> None:
    """Test setting up and unloading an air-quality entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST},
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.haven.HavenClient") as client_class:
        client = AsyncMock()
        client.get_info.return_value = DeviceInfo.from_dict(TEST_INFO)
        client.get_sensors.return_value = SensorData.from_dict(TEST_SENSORS)
        client_class.return_value = client

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        client.get_sensors.assert_awaited_once()
        client.get_status.assert_not_awaited()
        client.get_controller.assert_not_awaited()
        assert await hass.config_entries.async_unload(entry.entry_id)
