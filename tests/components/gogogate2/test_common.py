"""Tests for common code."""
from datetime import timedelta
from unittest.mock import MagicMock

from homeassistant.components.gogogate2 import get_api
from homeassistant.components.gogogate2.common import DataManager
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_data_manager_polling(hass: HomeAssistant) -> None:
    """Test polling of data manager."""
    config_entry = MockConfigEntry(
        unique_id="abcdefg",
        options={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_USERNAME: "myusername",
            CONF_PASSWORD: "mypassword",
        },
    )

    config_entry.add_to_hass(hass)

    api = get_api(config_entry.options)
    api.info = MagicMock()

    data_manager = DataManager(hass, api, config_entry)

    start_time = dt_util.now()
    data_manager.start_polling()
    async_fire_time_changed(hass, start_time + timedelta(seconds=5.1))
    await hass.async_block_till_done()
    api.info.assert_called_once()

    api.info.reset_mock()
    async_fire_time_changed(hass, start_time + timedelta(seconds=5.1))
    await hass.async_block_till_done()
    api.info.assert_called_once()

    api.info.reset_mock()
    data_manager.stop_polling()
    async_fire_time_changed(hass, start_time + timedelta(seconds=5.1))
    await hass.async_block_till_done()
    api.info.assert_not_called()

    data_manager.stop_polling()
