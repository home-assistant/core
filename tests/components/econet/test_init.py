"""Tests for the Econet component."""

from pyeconet import EcoNetApiInterface, EquipmentType
from pyeconet.equipments.water_heater import WaterHeater, WaterHeaterOperationMode
from pyeconet.errors import InvalidCredentialsError
import pytest

from homeassistant.components.econet import async_setup_entry, async_unload_entry
from homeassistant.components.econet.const import DOMAIN
from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    STATE_ELECTRIC,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_USERNAME,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component

from tests.async_mock import AsyncMock, MagicMock, patch
from tests.common import MockConfigEntry


@patch("homeassistant.components.econet.common.EcoNetApiInterface")
async def test_setup(econetapi_mock, hass: HomeAssistant) -> None:
    """Test config setup where the config is updated."""

    # Setup the API.
    water_heater_1 = MagicMock(WaterHeater)
    water_heater_1.active = True
    water_heater_1.supports_away = True
    water_heater_1.away = False
    water_heater_1.connected = True
    water_heater_1.device_name = "Water Heater 1"
    water_heater_1.device_id = "WH1"
    water_heater_1.generic_type = "TYPE"
    water_heater_1.vacation = False
    water_heater_1.type = EquipmentType.WATER_HEATER
    water_heater_1.serial_number = "123456"
    water_heater_1.alert_count = 0
    water_heater_1.set_point = 120
    water_heater_1.set_point_limits = (110, 125)
    water_heater_1.wifi_signal = 123

    water_heater_1.leak_installed = True
    water_heater_1.has_shutoff_valve = True
    water_heater_1.running = True
    water_heater_1.tank_hot_water_availability = 40
    water_heater_1.shutoff_valve_open = False
    water_heater_1.tank_health = 90
    water_heater_1.modes = [
        WaterHeaterOperationMode.ELECTRIC_MODE,
        WaterHeaterOperationMode.OFF,
    ]
    water_heater_1.mode = WaterHeaterOperationMode.ELECTRIC_MODE
    water_heater_1.enabled = True
    water_heater_1.override_status = ""
    water_heater_1.todays_energy_usage = 1.23
    water_heater_1.get_energy_usage = AsyncMock()

    api = MagicMock(EcoNetApiInterface)
    api.get_equipment_by_type = AsyncMock(
        return_value={EquipmentType.WATER_HEATER: [water_heater_1]}
    )
    econetapi_mock.login = AsyncMock(return_value=api)

    # Setup the component. Import the config.
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            WATER_HEATER_DOMAIN: [
                {
                    CONF_PLATFORM: DOMAIN,
                    # Using CONF_USERNAME but the config uses CONF_EMAIL.
                    # This is to maintain compatibility with older configurations.
                    CONF_USERNAME: "admin@localhost.com",
                    CONF_PASSWORD: "password",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    # Assert the config entry was created.
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    api.subscribe.assert_called()

    # Assert the states for the equipment is set.
    states = hass.states.async_all(WATER_HEATER_DOMAIN)
    assert states
    assert len(states) == 1
    state = states[0]
    assert state
    assert state.attributes["min_temp"] == 43.3
    assert state.attributes["max_temp"] == 51.7
    assert state.attributes["operation_list"] == [STATE_ELECTRIC, STATE_OFF]
    assert state.attributes["current_temperature"] is None
    assert state.attributes["temperature"] == 48.9
    assert state.attributes["target_temp_high"] is None
    assert state.attributes["target_temp_low"] is None
    assert state.attributes["operation_mode"] == STATE_ELECTRIC
    assert state.attributes["on_vacation"] is False
    assert state.attributes["todays_energy_usage"] == 1.23
    assert state.attributes["in_use"] is True
    assert state.attributes["lower_temp"] == 110
    assert state.attributes["upper_temp"] == 125
    assert state.attributes["is_enabled"] is True
    assert state.attributes["friendly_name"] == "Water Heater 1"
    assert state.attributes["supported_features"] == 3

    # Call services on the entity.
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: state.entity_id,
            ATTR_TEMPERATURE: 12.34,
            ATTR_OPERATION_MODE: STATE_ELECTRIC,
        },
    )
    await hass.async_block_till_done()
    water_heater_1.set_set_point.assert_called_with(54.212)
    water_heater_1.set_mode.assert_called_with(WaterHeaterOperationMode.ELECTRIC_MODE)

    water_heater_1.set_set_point.reset_mock()
    water_heater_1.set_mode.reset_mock()
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: state.entity_id,
            ATTR_OPERATION_MODE: STATE_OFF,
        },
    )
    await hass.async_block_till_done()
    water_heater_1.set_mode.assert_called_with(WaterHeaterOperationMode.OFF)

    # Confirm updates to the update calback update the state.
    update_callback = water_heater_1.set_update_callback.call_args_list[0][0][0]
    water_heater_1.mode = WaterHeaterOperationMode.OFF
    assert hass.states.get(state.entity_id).state == STATE_ELECTRIC
    update_callback()
    await hass.async_block_till_done()
    assert hass.states.get(state.entity_id).state == STATE_OFF

    # Unload the component.
    await async_unload_entry(hass, config_entry)
    api.unsubscribe.assert_called()


@patch("homeassistant.components.econet.common.EcoNetApiInterface")
async def test_auth_fail(econetapi_mock, hass: HomeAssistant) -> None:
    """Test authorization failures."""

    api = MagicMock(EcoNetApiInterface)
    api.get_equipment_by_type = AsyncMock(return_value={})
    econetapi_mock.login = AsyncMock(side_effect=InvalidCredentialsError())

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_EMAIL: "admin@localhost.com",
            CONF_PASSWORD: "password",
        },
    )
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry_id=config_entry.entry_id)
    await hass.async_block_till_done()


@patch("homeassistant.components.econet.common.EcoNetApiInterface")
async def test_connection_fail(econetapi_mock, hass: HomeAssistant) -> None:
    """Test authorization failures."""

    api = MagicMock(EcoNetApiInterface)
    api.get_equipment_by_type = AsyncMock(return_value={})
    econetapi_mock.login = AsyncMock(side_effect=[Exception("Connection failed."), api])

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_EMAIL: "admin@localhost.com",
            CONF_PASSWORD: "password",
        },
    )
    config_entry.add_to_hass(hass)

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, config_entry)
