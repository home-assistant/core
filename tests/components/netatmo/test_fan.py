"""The tests for Netatmo switch."""
from unittest.mock import patch

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN, SERVICE_SET_PRESET_MODE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .common import selected_platforms


async def test_switch_setup_and_services(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test setup and services."""
    with selected_platforms([Platform.FAN]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    fan_entity = "fan.centralized_ventilation_controler"

    assert hass.states.get(fan_entity).state == "on"
    assert hass.states.get(fan_entity).attributes[ATTR_PRESET_MODE] == "slow"

    # Test turning switch on
    with patch("pyatmo.home.Home.async_set_state") as mock_set_state:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: fan_entity, ATTR_PRESET_MODE: "fast"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            {
                "modules": [
                    {
                        "id": "12:34:56:00:01:01:01:b1",
                        "fan_speed": 2,
                        "bridge": "12:34:56:80:60:40",
                    }
                ]
            }
        )
