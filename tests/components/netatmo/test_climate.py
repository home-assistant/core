"""The tests for the Netatmo climate platform."""
from unittest.mock import patch

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
    PRESET_AWAY,
    PRESET_BOOST,
    HVACMode,
)
from homeassistant.components.netatmo.climate import PRESET_FROST_GUARD, PRESET_SCHEDULE
from homeassistant.components.netatmo.const import (
    ATTR_SCHEDULE_NAME,
    SERVICE_SET_SCHEDULE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, CONF_WEBHOOK_ID

from .common import selected_platforms, simulate_webhook


async def test_webhook_event_handling_thermostats(hass, config_entry, netatmo_auth):
    """Test service and webhook event handling with thermostats."""
    with selected_platforms(["climate"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_livingroom = "climate.livingroom"

    assert hass.states.get(climate_entity_livingroom).state == "auto"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"]
        == "Schedule"
    )
    assert hass.states.get(climate_entity_livingroom).attributes["temperature"] == 12

    # Test service setting the temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_TEMPERATURE: 21},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Fake webhook thermostat manual set point
    response = {
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
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_livingroom).state == "heat"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"]
        == "Schedule"
    )
    assert hass.states.get(climate_entity_livingroom).attributes["temperature"] == 21

    # Test service setting the HVAC mode to "heat"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Fake webhook thermostat mode change to "Max"
    response = {
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
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_livingroom).state == "heat"
    assert hass.states.get(climate_entity_livingroom).attributes["temperature"] == 30

    # Test service setting the HVAC mode to "off"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Fake webhook turn thermostat off
    response = {
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
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_livingroom).state == "off"

    # Test service setting the HVAC mode to "auto"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_HVAC_MODE: HVACMode.AUTO},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Fake webhook thermostat mode cancel set point
    response = {
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
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_livingroom).state == "auto"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"]
        == "Schedule"
    )


async def test_service_preset_mode_frost_guard_thermostat(
    hass, config_entry, netatmo_auth
):
    """Test service with frost guard preset for thermostats."""
    with selected_platforms(["climate"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_livingroom = "climate.livingroom"

    assert hass.states.get(climate_entity_livingroom).state == "auto"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"]
        == "Schedule"
    )

    # Test service setting the preset mode to "frost guard"
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

    # Fake webhook thermostat mode change to "Frost Guard"
    response = {
        "event_type": "therm_mode",
        "home": {"id": "91763b24c43d3e344f424e8b", "therm_mode": "hg"},
        "mode": "hg",
        "previous_mode": "schedule",
        "push_type": "home_event_changed",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_livingroom).state == "auto"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"]
        == "Frost Guard"
    )

    # Test service setting the preset mode to "frost guard"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: climate_entity_livingroom,
            ATTR_PRESET_MODE: PRESET_SCHEDULE,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Test webhook thermostat mode change to "Schedule"
    response = {
        "event_type": "therm_mode",
        "home": {"id": "91763b24c43d3e344f424e8b", "therm_mode": "schedule"},
        "mode": "schedule",
        "previous_mode": "hg",
        "push_type": "home_event_changed",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_livingroom).state == "auto"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"]
        == "Schedule"
    )


async def test_service_preset_modes_thermostat(hass, config_entry, netatmo_auth):
    """Test service with preset modes for thermostats."""
    with selected_platforms(["climate"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_livingroom = "climate.livingroom"

    assert hass.states.get(climate_entity_livingroom).state == "auto"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"]
        == "Schedule"
    )

    # Test service setting the preset mode to "away"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Fake webhook thermostat mode change to "Away"
    response = {
        "event_type": "therm_mode",
        "home": {"id": "91763b24c43d3e344f424e8b", "therm_mode": "away"},
        "mode": "away",
        "previous_mode": "schedule",
        "push_type": "home_event_changed",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_livingroom).state == "auto"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"] == "away"
    )

    # Test service setting the preset mode to "boost"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_PRESET_MODE: PRESET_BOOST},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Test webhook thermostat mode change to "Max"
    response = {
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
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_livingroom).state == "heat"
    assert hass.states.get(climate_entity_livingroom).attributes["temperature"] == 30


async def test_webhook_event_handling_no_data(hass, config_entry, netatmo_auth):
    """Test service and webhook event handling with erroneous data."""
    with selected_platforms(["climate"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    # Test webhook without home entry
    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    response = {
        "push_type": "home_event_changed",
    }
    await simulate_webhook(hass, webhook_id, response)

    # Test webhook with different home id
    response = {
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
    await simulate_webhook(hass, webhook_id, response)

    # Test webhook without room entries
    response = {
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
    await simulate_webhook(hass, webhook_id, response)


async def test_service_schedule_thermostats(hass, config_entry, caplog, netatmo_auth):
    """Test service for selecting Netatmo schedule with thermostats."""
    with selected_platforms(["climate"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_livingroom = "climate.livingroom"

    # Test setting a valid schedule
    with patch(
        "pyatmo.climate.AsyncClimate.async_switch_home_schedule"
    ) as mock_switch_home_schedule:
        await hass.services.async_call(
            "netatmo",
            SERVICE_SET_SCHEDULE,
            {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_SCHEDULE_NAME: "Winter"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_switch_home_schedule.assert_called_once_with(
            schedule_id="b1b54a2f45795764f59d50d8"
        )

    # Fake backend response for valve being turned on
    response = {
        "event_type": "schedule",
        "schedule_id": "b1b54a2f45795764f59d50d8",
        "previous_schedule_id": "59d32176d183948b05ab4dce",
        "push_type": "home_event_changed",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert (
        hass.states.get(climate_entity_livingroom).attributes["selected_schedule"]
        == "Winter"
    )

    # Test setting an invalid schedule
    with patch(
        "pyatmo.climate.AsyncClimate.async_switch_home_schedule"
    ) as mock_switch_home_schedule:
        await hass.services.async_call(
            "netatmo",
            SERVICE_SET_SCHEDULE,
            {ATTR_ENTITY_ID: climate_entity_livingroom, ATTR_SCHEDULE_NAME: "summer"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_switch_home_schedule.assert_not_called()

    assert "summer is not a valid schedule" in caplog.text


async def test_service_preset_mode_already_boost_valves(
    hass, config_entry, netatmo_auth
):
    """Test service with boost preset for valves when already in boost mode."""
    with selected_platforms(["climate"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_entrada = "climate.entrada"

    assert hass.states.get(climate_entity_entrada).state == "auto"
    assert (
        hass.states.get(climate_entity_entrada).attributes["preset_mode"]
        == "Frost Guard"
    )
    assert hass.states.get(climate_entity_entrada).attributes["temperature"] == 7

    # Test webhook valve mode change to "Max"
    response = {
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
    await simulate_webhook(hass, webhook_id, response)

    # Test service setting the preset mode to "boost"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: climate_entity_entrada, ATTR_PRESET_MODE: PRESET_BOOST},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Test webhook valve mode change to "Max"
    response = {
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
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_entrada).state == "heat"
    assert hass.states.get(climate_entity_entrada).attributes["temperature"] == 30


async def test_service_preset_mode_boost_valves(hass, config_entry, netatmo_auth):
    """Test service with boost preset for valves."""
    with selected_platforms(["climate"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_entrada = "climate.entrada"

    # Test service setting the preset mode to "boost"
    assert hass.states.get(climate_entity_entrada).state == "auto"
    assert hass.states.get(climate_entity_entrada).attributes["temperature"] == 7

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: climate_entity_entrada, ATTR_PRESET_MODE: PRESET_BOOST},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Fake backend response
    response = {
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
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_entrada).state == "heat"
    assert hass.states.get(climate_entity_entrada).attributes["temperature"] == 30


async def test_service_preset_mode_invalid(hass, config_entry, caplog, netatmo_auth):
    """Test service with invalid preset."""
    with selected_platforms(["climate"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "climate.cocina", ATTR_PRESET_MODE: "invalid"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert "Preset mode 'invalid' not available" in caplog.text


async def test_valves_service_turn_off(hass, config_entry, netatmo_auth):
    """Test service turn off for valves."""
    with selected_platforms(["climate"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_entrada = "climate.entrada"

    assert hass.states.get(climate_entity_entrada).attributes["hvac_modes"] == [
        "auto",
        "heat",
    ]

    # Test turning valve off
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: climate_entity_entrada},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Fake backend response for valve being turned off
    response = {
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
                    "therm_setpoint_mode": "off",
                }
            ],
            "modules": [{"id": "12:34:56:00:01:ae", "name": "Entrada", "type": "NRV"}],
        },
        "mode": "off",
        "event_type": "set_point",
        "push_type": "display_change",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_entrada).state == "off"


async def test_valves_service_turn_on(hass, config_entry, netatmo_auth):
    """Test service turn on for valves."""
    with selected_platforms(["climate"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_entrada = "climate.entrada"

    # Test turning valve on
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: climate_entity_entrada},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Fake backend response for valve being turned on
    response = {
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
                    "therm_setpoint_mode": "home",
                }
            ],
            "modules": [{"id": "12:34:56:00:01:ae", "name": "Entrada", "type": "NRV"}],
        },
        "mode": "home",
        "event_type": "cancel_set_point",
        "push_type": "display_change",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_entrada).state == "auto"


async def test_webhook_home_id_mismatch(hass, config_entry, netatmo_auth):
    """Test service turn on for valves."""
    with selected_platforms(["climate"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_entrada = "climate.entrada"

    assert hass.states.get(climate_entity_entrada).state == "auto"

    # Fake backend response for valve being turned on
    response = {
        "room_id": "2833524037",
        "home": {
            "id": "123",
            "name": "MYHOME",
            "country": "DE",
            "rooms": [
                {
                    "id": "2833524037",
                    "name": "Entrada",
                    "type": "lobby",
                    "therm_setpoint_mode": "home",
                }
            ],
            "modules": [{"id": "12:34:56:00:01:ae", "name": "Entrada", "type": "NRV"}],
        },
        "mode": "home",
        "event_type": "cancel_set_point",
        "push_type": "display_change",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_entrada).state == "auto"


async def test_webhook_set_point(hass, config_entry, netatmo_auth):
    """Test service turn on for valves."""
    with selected_platforms(["climate"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_entrada = "climate.entrada"

    # Fake backend response for valve being turned on
    response = {
        "room_id": "2746182631",
        "home": {
            "id": "91763b24c43d3e344f424e8b",
            "name": "MYHOME",
            "country": "DE",
            "rooms": [
                {
                    "id": "2833524037",
                    "name": "Entrada",
                    "type": "lobby",
                    "therm_setpoint_mode": "home",
                    "therm_setpoint_temperature": 30,
                }
            ],
            "modules": [{"id": "12:34:56:00:01:ae", "name": "Entrada", "type": "NRV"}],
        },
        "mode": "home",
        "event_type": "set_point",
        "temperature": 21,
        "push_type": "display_change",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_entrada).state == "heat"
