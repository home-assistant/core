"""Test the Kostal Plenticore Solar Inverter select platform."""
from unittest.mock import Mock

from kostal.plenticore import PlenticoreApiClient, SettingsData

from homeassistant.components.kostal_plenticore.const import DOMAIN
from homeassistant.components.kostal_plenticore.helper import Plenticore
from homeassistant.components.kostal_plenticore.select import async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from tests.common import MockConfigEntry


async def test_select(hass: HomeAssistant, mock_config_entry: MockConfigEntry):
    """Test that select entities are added."""

    plenticore: Plenticore = Mock(spec=Plenticore)
    hass.data[DOMAIN] = {mock_config_entry.entry_id: plenticore}
    plenticore.device_info = DeviceInfo()

    plenticore_client: PlenticoreApiClient = Mock(spec=PlenticoreApiClient)
    plenticore.client = plenticore_client

    # return all data ids which are needed by select platform
    plenticore_client.get_settings.return_value = {
        "devices:local": [
            SettingsData({"id": "Battery:SmartBatteryControl:Enable"}),
            SettingsData({"id": "Battery:TimeControl:Enable"}),
        ]
    }

    async_add_entities = Mock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    async_add_entities.assert_called_once()
    assert len(async_add_entities.call_args.args[0]) == 1


async def test_select_not_available(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
):
    """Test that select entities are not added if data ids are not available."""

    plenticore: Plenticore = Mock(spec=Plenticore)
    hass.data[DOMAIN] = {mock_config_entry.entry_id: plenticore}
    plenticore.device_info = DeviceInfo()

    plenticore_client: PlenticoreApiClient = Mock(spec=PlenticoreApiClient)
    plenticore.client = plenticore_client

    plenticore_client.get_settings.return_value = {
        "devices:local": [
            SettingsData({"id": "Battery:SmartBatteryControl:Enable"}),
        ]
    }

    async_add_entities = Mock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    async_add_entities.assert_called_once()
    assert len(async_add_entities.call_args.args[0]) == 0
