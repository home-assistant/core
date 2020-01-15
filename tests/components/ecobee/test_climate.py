"""Tests for the ecobee climate module."""
from unittest.mock import Mock

from asynctest import CoroutineMock, patch
import pyecobee
from pyecobee.const import ECOBEE_MODEL_TO_NAME
import pytest

from homeassistant.components import climate, ecobee
from homeassistant.components.ecobee.climate import Thermostat
from homeassistant.const import STATE_OFF, STATE_ON, TEMP_FAHRENHEIT

from tests.common import MockConfigEntry

MOCK_API_RESPONSE = [
    {
        "identifier": "test-identifier-1",
        "name": "Test Thermostat 1",
        "modelNumber": "athenaSmart",
        "settings": {
            "hvacMode": "heat",
            "coolStages": 1,
            "heatStages": 2,
            "fanMinOnTime": 5,
            "heatCoolMinDelta": 50,
            "holdAction": "indefinite",
        },
        "runtime": {
            "connected": True,
            "actualTemperature": 727,
            "actualHumidity": 35,
            "desiredHeat": 753,
            "desiredCool": 734,
            "desiredFanMode": "auto",
        },
        "events": [
            {"type": "hold", "name": "hold", "running": True, "holdClimateRef": ""},
            {
                "type": "template",
                "name": "_Default_",
                "running": False,
                "holdClimateRef": "",
            },
        ],
        "program": {
            "climates": [
                {"name": "Home", "climateRef": "home"},
                {"name": "Away", "climateRef": "away"},
                {"name": "Sleep", "climateRef": "sleep"},
            ],
            "currentClimateRef": "home",
        },
        "equipmentStatus": "auxHeat2,fan",
    },
    {
        "identifier": "test-identifier-2",
        "name": "Test Thermostat 2",
        "modelNumber": "badmodel",
        "settings": {
            "hvacMode": "auto",
            "coolStages": 0,
            "heatStages": 0,
            "fanMinOnTime": 5,
            "heatCoolMinDelta": 50,
            "holdAction": "indefinite",
        },
        "runtime": {
            "connected": True,
            "actualTemperature": 727,
            "actualHumidity": 35,
            "desiredHeat": 753,
            "desiredCool": 734,
            "desiredFanMode": "auto",
        },
        "events": [
            {"type": "hold", "name": "hold", "running": False, "holdClimateRef": ""},
            {
                "type": "vacation",
                "name": "test-vacation",
                "running": True,
                "holdClimateRef": "",
            },
            {
                "type": "template",
                "name": "_Default_",
                "running": False,
                "holdClimateRef": "",
            },
        ],
        "program": {
            "climates": [
                {"name": "Home", "climateRef": "home"},
                {"name": "Away", "climateRef": "away"},
                {"name": "Sleep", "climateRef": "sleep"},
            ],
            "currentClimateRef": "home",
        },
        "equipmentStatus": "auxHeat2",
    },
    {
        "identifier": "test-identifier-3",
        "name": "Test Thermostat 3",
        "modelNumber": "athenaSmart",
        "settings": {
            "hvacMode": "cool",
            "coolStages": 0,
            "heatStages": 0,
            "fanMinOnTime": 5,
            "heatCoolMinDelta": 50,
            "holdAction": "indefinite",
        },
        "runtime": {
            "connected": True,
            "actualTemperature": 727,
            "actualHumidity": 35,
            "desiredHeat": 753,
            "desiredCool": 734,
            "desiredFanMode": "auto",
        },
        "events": [
            {"type": "autoAway", "name": "away", "running": True, "holdClimateRef": ""},
            {
                "type": "template",
                "name": "_Default_",
                "running": False,
                "holdClimateRef": "",
            },
        ],
        "program": {
            "climates": [
                {"name": "Home", "climateRef": "home"},
                {"name": "Away", "climateRef": "away"},
                {"name": "Sleep", "climateRef": "sleep"},
            ],
            "currentClimateRef": "home",
        },
        "equipmentStatus": "",
    },
    {
        "identifier": "test-identifier-4",
        "name": "Test Thermostat 4",
        "modelNumber": "athenaSmart",
        "settings": {
            "hvacMode": "cool",
            "coolStages": 0,
            "heatStages": 0,
            "fanMinOnTime": 5,
            "heatCoolMinDelta": 50,
            "holdAction": "indefinite",
        },
        "runtime": {
            "connected": True,
            "actualTemperature": 727,
            "actualHumidity": 35,
            "desiredHeat": 753,
            "desiredCool": 734,
            "desiredFanMode": "auto",
        },
        "events": [
            {"type": "hold", "name": "Home", "running": True, "holdClimateRef": "home"},
            {
                "type": "template",
                "name": "_Default_",
                "running": False,
                "holdClimateRef": "",
            },
        ],
        "program": {
            "climates": [
                {"name": "Home", "climateRef": "home"},
                {"name": "Away", "climateRef": "away"},
                {"name": "Sleep", "climateRef": "sleep"},
            ],
            "currentClimateRef": "home",
        },
        "equipmentStatus": "humidifier",
    },
    {
        "identifier": "test-identifier-5",
        "name": "Test Thermostat 5",
        "modelNumber": "athenaSmart",
        "settings": {
            "hvacMode": "cool",
            "coolStages": 0,
            "heatStages": 0,
            "fanMinOnTime": 5,
            "heatCoolMinDelta": 50,
            "holdAction": "nextTransition",
        },
        "runtime": {
            "connected": True,
            "actualTemperature": 727,
            "actualHumidity": 35,
            "desiredHeat": 753,
            "desiredCool": 734,
            "desiredFanMode": "auto",
        },
        "events": [
            {
                "type": "sensor",
                "name": "Living Room",
                "running": True,
                "holdClimateRef": "",
            },
            {
                "type": "template",
                "name": "_Default_",
                "running": False,
                "holdClimateRef": "",
            },
        ],
        "program": {
            "climates": [
                {"name": "Home", "climateRef": "home"},
                {"name": "Away", "climateRef": "away"},
                {"name": "Sleep", "climateRef": "sleep"},
            ],
            "currentClimateRef": "sleep",
        },
        "equipmentStatus": "auxHeat2,fan",
    },
]


@pytest.fixture
def mock_account(hass):
    """Mock an ecobee account object."""
    account = ecobee.EcobeeData(
        hass,
        MockConfigEntry(domain=ecobee.DOMAIN),
        api_key="dummy",
        refresh_token="dummy",
    )

    def mock_get_thermostat(index):
        return account.ecobee.thermostats[index]

    account.ecobee = Mock(
        thermostats=MOCK_API_RESPONSE,
        get_thermostat=mock_get_thermostat,
        spec=pyecobee.Ecobee,
    )

    return account


async def setup_climate(hass, mock_account):
    """Load the ecobee climate platform with the mocked account."""
    hass.config.components.add(ecobee.DOMAIN)
    hass.data[ecobee.DOMAIN] = mock_account
    config_entry = MockConfigEntry(domain=ecobee.DOMAIN)
    await hass.config_entries.async_forward_entry_setup(config_entry, "climate")


async def test_climate_platform_loads_correctly(hass, mock_account):
    """Test that the climate platform loads with five climate entities."""
    await setup_climate(hass, mock_account)
    assert len(hass.states.async_all()) == 5
    t_stat_1 = hass.states.get("climate.test_thermostat_1")
    assert t_stat_1 is not None
    t_stat_2 = hass.states.get("climate.test_thermostat_2")
    assert t_stat_2 is not None
    t_stat_3 = hass.states.get("climate.test_thermostat_3")
    assert t_stat_3 is not None
    t_stat_4 = hass.states.get("climate.test_thermostat_4")
    assert t_stat_4 is not None
    t_stat_5 = hass.states.get("climate.test_thermostat_5")
    assert t_stat_5 is not None


async def test_simple_properties(mock_account):
    """Test that a climate entity returns expected values for simple properties."""
    t_stat = Thermostat(mock_account, 0)
    assert t_stat.available is True
    assert t_stat.supported_features == ecobee.climate.SUPPORT_FLAGS
    assert t_stat.name == "Test Thermostat 1"
    assert t_stat.unique_id == "test-identifier-1"
    assert t_stat.temperature_unit == TEMP_FAHRENHEIT
    assert t_stat.current_temperature == 72.7
    assert t_stat.fan_mode == "auto"
    assert t_stat.fan_modes == [climate.const.FAN_AUTO, climate.const.FAN_ON]
    assert t_stat.preset_modes == ["Home", "Away", "Sleep"]
    assert t_stat.hvac_mode == "heat"
    assert t_stat.current_humidity == 35
    assert t_stat.device_state_attributes == {
        "fan": STATE_ON,
        "climate_mode": "Home",
        "equipment_running": "auxHeat2,fan",
        "fan_min_on_time": 5,
    }
    assert t_stat.is_aux_heat is True


async def test_device_info_property(mock_account):
    """Test the device_info property."""
    t_stat_1 = Thermostat(mock_account, 0)
    assert t_stat_1.device_info == {
        "identifiers": {("ecobee", "test-identifier-1")},
        "name": "Test Thermostat 1",
        "manufacturer": "ecobee",
        "model": ECOBEE_MODEL_TO_NAME["athenaSmart"],
    }
    t_stat_2 = Thermostat(mock_account, 1)
    assert t_stat_2.device_info is None


async def test_target_temperature_low_property(mock_account):
    """Test the target_temperature_low property."""
    t_stat_1 = Thermostat(mock_account, 0)
    assert t_stat_1.target_temperature_low is None
    t_stat_2 = Thermostat(mock_account, 1)
    assert t_stat_2.target_temperature_low == 75.3


async def test_target_temperature_high_property(mock_account):
    """Test the target_temperature_high property."""
    t_stat_1 = Thermostat(mock_account, 0)
    assert t_stat_1.target_temperature_high is None
    t_stat_2 = Thermostat(mock_account, 1)
    assert t_stat_2.target_temperature_high == 73.4


async def test_target_temperature_property(mock_account):
    """Test the target_temperature property."""
    t_stat_1 = Thermostat(mock_account, 0)
    assert t_stat_1.target_temperature == 75.3
    t_stat_2 = Thermostat(mock_account, 2)
    assert t_stat_2.target_temperature == 73.4
    t_stat_3 = Thermostat(mock_account, 1)
    assert t_stat_3.target_temperature is None


async def test_fan_property(mock_account):
    """Test the fan property."""
    t_stat_1 = Thermostat(mock_account, 0)
    assert t_stat_1.fan == STATE_ON
    t_stat_2 = Thermostat(mock_account, 1)
    assert t_stat_2.fan == STATE_OFF


async def test_preset_mode_property(mock_account):
    """Test the preset mode property."""
    t_stat_1 = Thermostat(mock_account, 0)
    assert t_stat_1.preset_mode == ecobee.const.PRESET_TEMPERATURE
    t_stat_2 = Thermostat(mock_account, 3)
    assert t_stat_2.preset_mode == "Home"
    t_stat_3 = Thermostat(mock_account, 2)
    assert t_stat_3.preset_mode == "away"
    t_stat_4 = Thermostat(mock_account, 1)
    assert t_stat_4.preset_mode == "vacation"
    t_stat_5 = Thermostat(mock_account, 4)
    assert t_stat_5.preset_mode == "Sleep"


async def test_hvac_modes_property(mock_account):
    """Test the hvac_modes property."""
    t_stat_1 = Thermostat(mock_account, 0)
    assert t_stat_1.hvac_modes == [
        climate.const.HVAC_MODE_AUTO,
        climate.const.HVAC_MODE_HEAT,
        climate.const.HVAC_MODE_COOL,
        climate.const.HVAC_MODE_OFF,
    ]
    t_stat_2 = Thermostat(mock_account, 1)
    assert t_stat_2.hvac_modes == [climate.const.HVAC_MODE_OFF]


async def test_hvac_action_property(mock_account):
    """Test the hvac_action property."""
    t_stat_1 = Thermostat(mock_account, 0)
    assert t_stat_1.hvac_action == climate.const.CURRENT_HVAC_HEAT

    t_stat_2 = Thermostat(mock_account, 2)
    assert t_stat_2.hvac_action == climate.const.CURRENT_HVAC_IDLE

    t_stat_3 = Thermostat(mock_account, 3)
    assert t_stat_3.hvac_action == climate.const.CURRENT_HVAC_IDLE


async def test_set_preset_mode(mock_account):
    """Test the async_set_preset_mode method."""
    pass


async def test_set_fan_mode(mock_account):
    """Test the async_set_fan_mode method."""
    with patch.object(mock_account.ecobee, "set_fan_mode") as mock_method:
        t_stat = Thermostat(mock_account, 0)
        await t_stat.async_set_fan_mode("dummy")
        mock_method.assert_not_called()

        await t_stat.async_set_fan_mode("auto")
        mock_method.assert_called_with(0, "auto", 73.4, 75.3, "nextTransition")


async def test_set_temperature(mock_account):
    """Test the async_set_temperature method."""
    pass


async def test_set_humidity(mock_account):
    """Test the async_set_humidity method."""
    with patch.object(mock_account.ecobee, "set_humidity") as mock_method:
        t_stat = Thermostat(mock_account, 0)

        await t_stat.async_set_humidity(50)
        mock_method.assert_called_with(0, 50)


async def test_set_hvac_mode(mock_account):
    """Test the async_set_hvac_mode method."""
    with patch.object(mock_account.ecobee, "set_hvac_mode") as mock_method:
        t_stat = Thermostat(mock_account, 0)

        await t_stat.async_set_hvac_mode("dummy")
        mock_method.assert_not_called()

        await t_stat.async_set_hvac_mode("auto")
        mock_method.assert_called_with(0, "auto")


async def test_turn_on(hass, mock_account):
    """Test the async_turn_on method."""
    with patch.object(mock_account.ecobee, "set_hvac_mode") as mock_method:
        await setup_climate(hass, mock_account)

        await hass.services.async_call(
            "climate",
            "turn_on",
            {"entity_id": "climate.test_thermostat_1"},
            blocking=True,
        )
        mock_method.assert_called_with(0, "heat")


async def test_turn_off(hass, mock_account):
    """Test the async_turn_off method."""
    with patch.object(mock_account.ecobee, "set_hvac_mode") as mock_method:
        await setup_climate(hass, mock_account)

        await hass.services.async_call(
            "climate",
            "turn_off",
            {"entity_id": "climate.test_thermostat_1"},
            blocking=True,
        )
        mock_method.assert_called_with(0, "off")


async def test_update(mock_account):
    """Test the async_update method."""
    with patch.object(
        mock_account, "update", new_callable=CoroutineMock
    ) as mock_method:
        t_stat = Thermostat(mock_account, 0)
        await t_stat.async_update()
        mock_method.assert_awaited()

        t_stat._update_without_throttle = True
        await t_stat.async_update()
        mock_method.assert_awaited_with(no_throttle=True)


async def test_set_auto_temp_hold(mock_account):
    """Test the set_auto_temp_hold method."""
    with patch.object(mock_account.ecobee, "set_hold_temp") as mock_method:
        t_stat = Thermostat(mock_account, 0)

        await t_stat.set_auto_temp_hold(None, None)
        mock_method.assert_called_with(0, 73.4, 75.3, "nextTransition")

        await t_stat.set_auto_temp_hold(75, 70)
        mock_method.assert_called_with(0, 70, 75, "nextTransition")


async def test_set_temp_hold(mock_account):
    """Test the set_temp_hold method."""
    t_stat_1 = Thermostat(mock_account, 0)
    with patch.object(
        t_stat_1, "set_auto_temp_hold", new_callable=CoroutineMock
    ) as mock_method:
        await t_stat_1.set_temp_hold(75)
        mock_method.assert_awaited_with(75, 75)

    t_stat_2 = Thermostat(mock_account, 1)
    with patch.object(
        t_stat_2, "set_auto_temp_hold", new_callable=CoroutineMock
    ) as mock_method:
        await t_stat_2.set_temp_hold(75)
        mock_method.assert_awaited_with(70, 80)


async def test_set_fan_min_on_time(mock_account):
    """Test the set_fan_min_on_time method."""
    with patch.object(mock_account.ecobee, "set_fan_min_on_time") as mock_method:
        t_stat = Thermostat(mock_account, 0)

        await t_stat.set_fan_min_on_time(10)
        mock_method.assert_called_with(0, 10)


async def test_resume_program(mock_account):
    """Test the resume_program method."""
    with patch.object(mock_account.ecobee, "resume_program") as mock_method:
        t_stat = Thermostat(mock_account, 0)

        await t_stat.resume_program()
        mock_method.assert_called_with(0, "false")

        await t_stat.resume_program(resume_all=True)
        mock_method.assert_called_with(0, "true")


async def test_hold_preference(mock_account):
    """Test the hold_preference method."""
    t_stat_1 = Thermostat(mock_account, 0)
    assert t_stat_1.hold_preference() == "nextTransition"

    t_stat_2 = Thermostat(mock_account, 4)
    assert t_stat_2.hold_preference() == "nextTransition"


async def test_create_vacation(hass, mock_account):
    """Test the create_vacation service."""
    with patch.object(mock_account.ecobee, "create_vacation") as mock_method:
        await setup_climate(hass, mock_account)

        await hass.services.async_call(
            "ecobee",
            "create_vacation",
            {
                "entity_id": "climate.test_thermostat_1",
                "vacation_name": "Skiing",
                "cool_temp": 23,
                "heat_temp": 25,
            },
            blocking=True,
        )
        mock_method.assert_called_with(
            0, "Skiing", 73.4, 77.0, fan_mode="auto", fan_min_on_time=0
        )

        await hass.services.async_call(
            "ecobee",
            "create_vacation",
            {
                "entity_id": "climate.test_thermostat_1",
                "vacation_name": "Beach",
                "cool_temp": 23,
                "heat_temp": 25,
                "start_date": "2019-11-19",
                "start_time": "08:00:00",
                "end_date": "2020-02-19",
                "end_time": "10:00:00",
                "fan_mode": "on",
                "fan_min_on_time": 5,
            },
            blocking=True,
        )
        mock_method.assert_called_with(
            0,
            "Beach",
            73.4,
            77.0,
            start_date="2019-11-19",
            start_time="08:00:00",
            end_date="2020-02-19",
            end_time="10:00:00",
            fan_mode="on",
            fan_min_on_time=5,
        )


async def test_delete_vacation(hass, mock_account):
    """Test the delete_vacation service."""
    with patch.object(mock_account.ecobee, "delete_vacation") as mock_method:
        await setup_climate(hass, mock_account)

        await hass.services.async_call(
            "ecobee",
            "delete_vacation",
            {"entity_id": "climate.test_thermostat_1", "vacation_name": "Skiing"},
            blocking=True,
        )
        mock_method.assert_called_with(0, "Skiing")
