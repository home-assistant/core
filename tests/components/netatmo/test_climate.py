"""The tests for the Netatmo climate platform."""
from unittest.mock import Mock

import pytest

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_BOOST,
)
from homeassistant.components.netatmo import climate
from homeassistant.components.netatmo.climate import (
    NA_THERM,
    NA_VALVE,
    PRESET_FROST_GUARD,
    PRESET_SCHEDULE,
)
from homeassistant.components.netatmo.const import (
    ATTR_SCHEDULE_NAME,
    SERVICE_SET_SCHEDULE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.helpers.dispatcher import async_dispatcher_send


async def test_setup_no_data(hass, entry_error):
    """Test ."""
    await hass.async_block_till_done()

    assert (
        "HomeData"
        not in hass.data["netatmo"][entry_error.entry_id]["netatmo_data_handler"].data
    )


async def test_setup_component(hass, entry):
    """Test ."""
    await hass.async_block_till_done()

    assert (
        "HomeData" in hass.data["netatmo"][entry.entry_id]["netatmo_data_handler"].data
    )

    climate_entity_livingroom = "climate.netatmo_livingroom"

    assert hass.states.get(climate_entity_livingroom).state == "auto"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"]
        == "Schedule"
    )

    # Test webhook thermostat manual set point
    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8b",
        "user": {"id": "91763b24c43d3e344f424e8b", "email": "john@doe.com"},
        "home_id": "91763b24c43d3e344f424e8b",
        "room_id": "2746182631",
        "home": {
            "id": "91763b24c43d3e344f424e8b",
            "name": "MYHOME",
            "country": "DE",
            "rooms": [
                {
                    "id": "2746182631",
                    "name": "Livingroom",
                    "type": "livingroom",
                    "therm_setpoint_mode": "manual",
                    "therm_setpoint_temperature": 21,
                    "therm_setpoint_end_time": 1612734552,
                }
            ],
            "modules": [
                {"id": "12:34:56:00:01:ae", "name": "Livingroom", "type": "NATherm1"}
            ],
        },
        "mode": "manual",
        "event_type": "set_point",
        "temperature": 21,
        "push_type": "display_change",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-set_point",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    assert hass.states.get(climate_entity_livingroom).state == "heat"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"]
        == "Schedule"
    )

    # Test webhook thermostat mode change to "Max"
    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8b",
        "user": {"id": "91763b24c43d3e344f424e8b", "email": "john@doe.com"},
        "home_id": "91763b24c43d3e344f424e8b",
        "room_id": "2746182631",
        "home": {
            "id": "91763b24c43d3e344f424e8b",
            "name": "MYHOME",
            "country": "DE",
            "rooms": [
                {
                    "id": "2746182631",
                    "name": "Livingroom",
                    "type": "livingroom",
                    "therm_setpoint_mode": "max",
                    "therm_setpoint_end_time": 1612749189,
                }
            ],
            "modules": [
                {"id": "12:34:56:00:01:ae", "name": "Livingroom", "type": "NATherm1"}
            ],
        },
        "mode": "max",
        "event_type": "set_point",
        "push_type": "display_change",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-set_point",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    assert hass.states.get(climate_entity_livingroom).state == "heat"

    # Test webhook turn thermostat off
    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8b",
        "user": {"id": "91763b24c43d3e344f424e8b", "email": "john@doe.com"},
        "home_id": "91763b24c43d3e344f424e8b",
        "room_id": "2746182631",
        "home": {
            "id": "91763b24c43d3e344f424e8b",
            "name": "MYHOME",
            "country": "DE",
            "rooms": [
                {
                    "id": "2746182631",
                    "name": "Livingroom",
                    "type": "livingroom",
                    "therm_setpoint_mode": "off",
                }
            ],
            "modules": [
                {"id": "12:34:56:00:01:ae", "name": "Livingroom", "type": "NATherm1"}
            ],
        },
        "mode": "off",
        "event_type": "set_point",
        "push_type": "display_change",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-set_point",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    assert hass.states.get(climate_entity_livingroom).state == "off"

    # Test webhook thermostat mode cancel set point
    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8b",
        "user": {"id": "91763b24c43d3e344f424e8b", "email": "john@doe.com"},
        "home_id": "91763b24c43d3e344f424e8b",
        "room_id": "2746182631",
        "home": {
            "id": "91763b24c43d3e344f424e8b",
            "name": "MYHOME",
            "country": "DE",
            "rooms": [
                {
                    "id": "2746182631",
                    "name": "Livingroom",
                    "type": "livingroom",
                    "therm_setpoint_mode": "home",
                }
            ],
            "modules": [
                {"id": "12:34:56:00:01:ae", "name": "Livingroom", "type": "NATherm1"}
            ],
        },
        "mode": "home",
        "event_type": "cancel_set_point",
        "push_type": "display_change",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-cancel_set_point",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    assert hass.states.get(climate_entity_livingroom).state == "auto"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"]
        == "Schedule"
    )

    # Test webhook thermostat mode change to "Frost Guard"
    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8b",
        "user": {"id": "91763b24c43d3e344f424e8b", "email": "john@doe.com"},
        "home_id": "91763b24c43d3e344f424e8b",
        "event_type": "therm_mode",
        "home": {"id": "91763b24c43d3e344f424e8b", "therm_mode": "hg"},
        "mode": "hg",
        "previous_mode": "schedule",
        "push_type": "home_event_changed",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-therm_mode",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    assert hass.states.get(climate_entity_livingroom).state == "auto"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"]
        == "Frost Guard"
    )

    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8b",
        "user": {"id": "91763b24c43d3e344f424e8b", "email": "john@doe.com"},
        "home_id": "91763b24c43d3e344f424e8b",
        "event_type": "therm_mode",
        "home": {"id": "91763b24c43d3e344f424e8b", "therm_mode": "schedule"},
        "mode": "schedule",
        "previous_mode": "hg",
        "push_type": "home_event_changed",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-therm_mode",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    assert hass.states.get(climate_entity_livingroom).state == "auto"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"]
        == "Schedule"
    )

    # Test webhook thermostat mode change to "Away"
    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8b",
        "user": {"id": "91763b24c43d3e344f424e8b", "email": "john@doe.com"},
        "home_id": "91763b24c43d3e344f424e8b",
        "event_type": "therm_mode",
        "home": {"id": "91763b24c43d3e344f424e8b", "therm_mode": "away"},
        "mode": "away",
        "previous_mode": "schedule",
        "push_type": "home_event_changed",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-therm_mode",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    assert hass.states.get(climate_entity_livingroom).state == "auto"
    # assert (
    #     hass.states.get(climate_entity_livingroom).attributes["preset_mode"] == "away"
    # )

    # Test webhook without home entry
    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8b",
        "user": {"id": "91763b24c43d3e344f424e8b", "email": "john@doe.com"},
        "home_id": "91763b24c43d3e344f424e8b",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-therm_mode",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    # Test webhook with different home id
    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8b",
        "user": {"id": "91763b24c43d3e344f424e8b", "email": "john@doe.com"},
        "home_id": "3d3e344f491763b24c424e8b",
        "room_id": "2746182631",
        "home": {
            "id": "3d3e344f491763b24c424e8b",
            "name": "MYHOME",
            "country": "DE",
            "rooms": [],
            "modules": [],
        },
        "mode": "home",
        "event_type": "cancel_set_point",
        "push_type": "display_change",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-therm_mode",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    # Test webhook without room entries
    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8b",
        "user": {"id": "91763b24c43d3e344f424e8b", "email": "john@doe.com"},
        "home_id": "91763b24c43d3e344f424e8b",
        "room_id": "2746182631",
        "home": {
            "id": "91763b24c43d3e344f424e8b",
            "name": "MYHOME",
            "country": "DE",
            "rooms": [],
            "modules": [],
        },
        "mode": "home",
        "event_type": "cancel_set_point",
        "push_type": "display_change",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-cancel_set_point",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_HVAC_MODE: HVAC_MODE_OFF},
        blocking=True,
    )
    await hass.async_block_till_done()

    # assert hass.states.get(climate_entity_livingroom).state == "off"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_HVAC_MODE: HVAC_MODE_AUTO},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(climate_entity_livingroom).state == "auto"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_HVAC_MODE: HVAC_MODE_HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()

    # assert hass.states.get(climate_entity_livingroom).state == "heat"

    # PRESET_AWAY, PRESET_BOOST, PRESET_FROST_GUARD, PRESET_SCHEDULE
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    await hass.async_block_till_done()

    # assert hass.states.get(climate_entity_livingroom).state == "heat"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_PRESET_MODE: PRESET_BOOST},
        blocking=True,
    )
    await hass.async_block_till_done()

    # assert hass.states.get(climate_entity_livingroom).state == "heat"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: climate_entity_livingroom,
            ATTR_PRESET_MODE: PRESET_FROST_GUARD,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # assert hass.states.get(climate_entity_livingroom).state == "heat"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_PRESET_MODE: PRESET_SCHEDULE},
        blocking=True,
    )
    await hass.async_block_till_done()

    # assert hass.states.get(climate_entity_livingroom).state == "heat"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_TEMPERATURE: 19},
        blocking=True,
    )
    await hass.async_block_till_done()

    # assert hass.states.get(climate_entity_livingroom).state == "heat"

    # Test setting a valid schedule
    await hass.services.async_call(
        "netatmo",
        SERVICE_SET_SCHEDULE,
        {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_SCHEDULE_NAME: "Winter"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Test setting an invalid schedule
    await hass.services.async_call(
        "netatmo",
        SERVICE_SET_SCHEDULE,
        {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_SCHEDULE_NAME: "summer"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # assert hass.states.get(climate_entity_livingroom).state == "heat"


async def test_valves(hass, climate_entry, caplog):
    """Test ."""
    await hass.async_block_till_done()

    assert (
        "HomeData"
        in hass.data["netatmo"][climate_entry.entry_id]["netatmo_data_handler"].data
    )

    climate_entity_entrada = "climate.netatmo_entrada"
    climate_entity_cocina = "climate.netatmo_cocina"

    assert hass.states.get(climate_entity_entrada).state == "auto"
    assert (
        hass.states.get(climate_entity_entrada).attributes["preset_mode"]
        == "Frost Guard"
    )

    # Test webhook thermostat mode change to "Max"
    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8b",
        "user": {"id": "91763b24c43d3e344f424e8b", "email": "john@doe.com"},
        "home_id": "91763b24c43d3e344f424e8b",
        "room_id": "2833524037",
        "home": {
            "id": "91763b24c43d3e344f424e8b",
            "name": "MYHOME",
            "country": "DE",
            "rooms": [
                {
                    "id": "2833524037",
                    "name": "Entrada",
                    "type": "lobby",
                    "therm_setpoint_mode": "max",
                    "therm_setpoint_end_time": 1612749189,
                }
            ],
            "modules": [{"id": "12:34:56:00:01:ae", "name": "Entrada", "type": "NRV"}],
        },
        "mode": "max",
        "event_type": "set_point",
        "push_type": "display_change",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-set_point",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    assert hass.states.get(climate_entity_entrada).state == "heat"

    #
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: climate_entity_entrada, ATTR_PRESET_MODE: PRESET_BOOST},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(climate_entity_entrada).state == "heat"

    #
    assert hass.states.get(climate_entity_cocina).state == "auto"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: climate_entity_cocina, ATTR_PRESET_MODE: PRESET_BOOST},
        blocking=True,
    )
    await hass.async_block_till_done()

    # assert hass.states.get(climate_entity_cocina).state == "heat"

    # Test setting invalid preset mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: climate_entity_cocina, ATTR_PRESET_MODE: "invalid"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert "Preset mode 'invalid' not available" in caplog.text

    # Test turning valve off
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: climate_entity_cocina},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Test turning valve on
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: climate_entity_cocina},
        blocking=True,
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "batterylevel, module_type, expected",
    [
        (4101, NA_THERM, 100),
        (3601, NA_THERM, 80),
        (3450, NA_THERM, 65),
        (3301, NA_THERM, 50),
        (3001, NA_THERM, 20),
        (2799, NA_THERM, 0),
        (3201, NA_VALVE, 100),
        (2701, NA_VALVE, 80),
        (2550, NA_VALVE, 65),
        (2401, NA_VALVE, 50),
        (2201, NA_VALVE, 20),
        (2001, NA_VALVE, 0),
    ],
)
async def test_interpolate(batterylevel, module_type, expected):
    """Test interpolation of battery levels depending on device type."""
    assert climate.interpolate(batterylevel, module_type) == expected


async def test_get_all_home_ids():
    """Test extracting all home ids returned by NetAtmo API."""
    assert climate.get_all_home_ids(None) == []

    home_data = Mock()
    home_data.homes = {
        "123": {"id": "123", "name": "Home 1", "modules": [], "therm_schedules": []},
        "987": {"id": "987", "name": "Home 2", "modules": [], "therm_schedules": []},
    }
    expected = ["123", "987"]
    assert climate.get_all_home_ids(home_data) == expected
