"""The tests for the Netatmo climate platform."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from probatio.error import MultipleInvalid
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    PRESET_BOOST,
    ClimateService,
    ClimateServiceArgument,
    HVACAction,
    HVACMode,
)
from homeassistant.components.netatmo.climate import PRESET_FROST_GUARD, PRESET_SCHEDULE
from homeassistant.components.netatmo.const import (
    DOMAIN,
    NetatmoService,
    NetatmoServiceArgument,
)
from homeassistant.const import CONF_WEBHOOK_ID, Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .common import (
    fake_get_image,
    fake_post_request,
    selected_platforms,
    simulate_webhook,
    snapshot_platform_entities,
)

CLIMATE_ENTITY_LIVINGROOM = "climate.livingroom_livingroom"


async def test_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(
        hass,
        config_entry,
        Platform.CLIMATE,
        entity_registry,
        snapshot,
    )


async def test_schedule_update_webhook_event(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test schedule update webhook event without schedule_id."""

    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_livingroom = "climate.livingroom_livingroom"

    # Save initial state
    initial_state = hass.states.get(climate_entity_livingroom)

    # Create a schedule update event without a schedule_id (the
    # event is sent when temperature sets of a schedule are changed)
    response = {
        "home_id": "91763b24c43d3e344f424e8b",
        "event_type": "schedule",
        "push_type": "home_event_changed",
    }
    await simulate_webhook(hass, webhook_id, response)

    # State should be unchanged
    assert hass.states.get(climate_entity_livingroom) == initial_state


async def test_webhook_event_handling_thermostats(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service and webhook event handling with thermostats."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_livingroom = "climate.livingroom_livingroom"

    assert hass.states.get(climate_entity_livingroom).state == "auto"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"] == "away"
    )
    assert hass.states.get(climate_entity_livingroom).attributes["temperature"] == 12

    # Test service setting the temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_TEMPERATURE,
        {
            TargetKey.ENTITY_ID: climate_entity_livingroom,
            ClimateServiceArgument.TEMPERATURE: 21,
        },
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
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"] == "away"
    )
    assert hass.states.get(climate_entity_livingroom).attributes["temperature"] == 21

    # Test service setting the HVAC mode to "heat"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_HVAC_MODE,
        {
            TargetKey.ENTITY_ID: climate_entity_livingroom,
            ClimateServiceArgument.HVAC_MODE: HVACMode.HEAT,
        },
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
        ClimateService.SET_HVAC_MODE,
        {
            TargetKey.ENTITY_ID: climate_entity_livingroom,
            ClimateServiceArgument.HVAC_MODE: HVACMode.OFF,
        },
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
        ClimateService.SET_HVAC_MODE,
        {
            TargetKey.ENTITY_ID: climate_entity_livingroom,
            ClimateServiceArgument.HVAC_MODE: HVACMode.AUTO,
        },
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
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"] == "away"
    )


async def test_service_preset_mode_frost_guard_thermostat(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service with frost guard preset for thermostats."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_livingroom = "climate.livingroom_livingroom"

    assert hass.states.get(climate_entity_livingroom).state == "auto"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"] == "away"
    )

    # Test service setting the preset mode to "frost guard"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: climate_entity_livingroom,
            ClimateServiceArgument.PRESET_MODE: PRESET_FROST_GUARD,
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
        == "frost_guard"
    )

    # Test service setting the preset mode to "frost guard"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: climate_entity_livingroom,
            ClimateServiceArgument.PRESET_MODE: PRESET_SCHEDULE,
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
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"] == "away"
    )


async def test_service_preset_modes_thermostat(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service with preset modes for thermostats."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_livingroom = "climate.livingroom_livingroom"

    assert hass.states.get(climate_entity_livingroom).state == "auto"
    assert (
        hass.states.get(climate_entity_livingroom).attributes["preset_mode"] == "away"
    )

    # Test service setting the preset mode to "away"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: climate_entity_livingroom,
            ClimateServiceArgument.PRESET_MODE: PRESET_AWAY,
        },
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
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: climate_entity_livingroom,
            ClimateServiceArgument.PRESET_MODE: PRESET_BOOST,
        },
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


async def test_service_set_temperature_with_end_datetime(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service setting temperature with an end datetime."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_livingroom = "climate.livingroom_livingroom"

    assert hass.states.get(climate_entity_livingroom).state == "auto"

    # Test service setting the temperature without an end datetime
    await hass.services.async_call(
        DOMAIN,
        NetatmoService.SET_TEMPERATURE_WITH_END_DATETIME,
        {
            TargetKey.ENTITY_ID: climate_entity_livingroom,
            NetatmoServiceArgument.TARGET_TEMPERATURE: 25,
            NetatmoServiceArgument.END_DATETIME: "2023-11-17 12:23:00",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Test webhook room mode change to "manual"
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
                    "therm_setpoint_temperature": 25,
                    "therm_setpoint_end_time": 1612749189,
                }
            ],
            "modules": [
                {"id": "12:34:56:00:01:ae", "name": "Livingroom", "type": "NATherm1"}
            ],
        },
        "mode": "manual",
        "event_type": "set_point",
        "push_type": "display_change",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_livingroom).state == "heat"
    assert hass.states.get(climate_entity_livingroom).attributes["temperature"] == 25


async def test_service_set_temperature_with_time_period(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service setting temperature with an end datetime."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_livingroom = "climate.livingroom_livingroom"

    assert hass.states.get(climate_entity_livingroom).state == "auto"

    # Test service setting the temperature without an end datetime
    await hass.services.async_call(
        DOMAIN,
        NetatmoService.SET_TEMPERATURE_WITH_TIME_PERIOD,
        {
            TargetKey.ENTITY_ID: climate_entity_livingroom,
            NetatmoServiceArgument.TARGET_TEMPERATURE: 25,
            NetatmoServiceArgument.TIME_PERIOD: "02:24:00",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Test webhook room mode change to "manual"
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
                    "therm_setpoint_temperature": 25,
                    "therm_setpoint_end_time": 1612749189,
                }
            ],
            "modules": [
                {"id": "12:34:56:00:01:ae", "name": "Livingroom", "type": "NATherm1"}
            ],
        },
        "mode": "manual",
        "event_type": "set_point",
        "push_type": "display_change",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_livingroom).state == "heat"
    assert hass.states.get(climate_entity_livingroom).attributes["temperature"] == 25


async def test_service_clear_temperature_setting(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service clearing temperature setting."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_livingroom = "climate.livingroom_livingroom"

    assert hass.states.get(climate_entity_livingroom).state == "auto"

    # Simulate a room thermostat change to manual boost
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
                    "therm_setpoint_temperature": 25,
                    "therm_setpoint_end_time": 1612749189,
                }
            ],
            "modules": [
                {"id": "12:34:56:00:01:ae", "name": "Livingroom", "type": "NATherm1"}
            ],
        },
        "mode": "manual",
        "event_type": "set_point",
        "push_type": "display_change",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(climate_entity_livingroom).state == "heat"
    assert hass.states.get(climate_entity_livingroom).attributes["temperature"] == 25

    # Test service setting the temperature without an end datetime
    await hass.services.async_call(
        DOMAIN,
        NetatmoService.CLEAR_TEMPERATURE_SETTING,
        {TargetKey.ENTITY_ID: climate_entity_livingroom},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Test webhook room mode change to "home"
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


async def test_webhook_event_handling_no_data(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service and webhook event handling with erroneous data."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

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


async def test_service_schedule_thermostats(
    hass: HomeAssistant, config_entry, caplog: pytest.LogCaptureFixture, netatmo_auth
) -> None:
    """Test service for selecting Netatmo schedule with thermostats."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_livingroom = "climate.livingroom_livingroom"

    assert (
        hass.states.get(climate_entity_livingroom).attributes.get(
            "selected_schedule_id"
        )
        == "591b54a2764ff4d50d8b5795"
    )

    # Test setting a valid schedule
    with patch("pyatmo.home.Home.async_switch_schedule") as mock_switch_schedule:
        await hass.services.async_call(
            "netatmo",
            NetatmoService.SET_SCHEDULE,
            {
                TargetKey.ENTITY_ID: climate_entity_livingroom,
                NetatmoServiceArgument.SCHEDULE_NAME: "Winter",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_switch_schedule.assert_called_once_with(
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
    assert (
        hass.states.get(climate_entity_livingroom).attributes.get(
            "selected_schedule_id"
        )
        == "b1b54a2f45795764f59d50d8"
    )

    # Test setting an invalid schedule
    with patch("pyatmo.home.Home.async_switch_schedule") as mock_switch_home_schedule:
        await hass.services.async_call(
            "netatmo",
            NetatmoService.SET_SCHEDULE,
            {
                TargetKey.ENTITY_ID: climate_entity_livingroom,
                NetatmoServiceArgument.SCHEDULE_NAME: "summer",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_switch_home_schedule.assert_not_called()

    assert "summer is not a valid schedule" in caplog.text


async def test_service_preset_mode_with_end_time_thermostats(
    hass: HomeAssistant, config_entry, caplog: pytest.LogCaptureFixture, netatmo_auth
) -> None:
    """Test service for set preset mode with end datetime for Netatmo thermostats."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_livingroom = "climate.livingroom_livingroom"

    # Test setting a valid preset mode (that allow an end datetime
    # in Netatmo == THERM_MODES) and a valid end datetime
    await hass.services.async_call(
        "netatmo",
        NetatmoService.SET_PRESET_MODE_WITH_END_DATETIME,
        {
            TargetKey.ENTITY_ID: climate_entity_livingroom,
            ATTR_PRESET_MODE: PRESET_AWAY,
            NetatmoServiceArgument.END_DATETIME: (
                dt_util.now() + timedelta(days=10)
            ).strftime("%Y-%m-%d %H:%M:%S"),
        },
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

    # Test setting an invalid preset mode (not in THERM_MODES) and a valid end datetime
    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(
            "netatmo",
            NetatmoService.SET_PRESET_MODE_WITH_END_DATETIME,
            {
                TargetKey.ENTITY_ID: climate_entity_livingroom,
                ATTR_PRESET_MODE: PRESET_BOOST,
                NetatmoServiceArgument.END_DATETIME: (
                    dt_util.now() + timedelta(days=10)
                ).strftime("%Y-%m-%d %H:%M:%S"),
            },
            blocking=True,
        )

    # Test setting a valid preset mode (that allow an end datetime
    # in Netatmo == THERM_MODES) without an end datetime
    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(
            "netatmo",
            NetatmoService.SET_PRESET_MODE_WITH_END_DATETIME,
            {
                TargetKey.ENTITY_ID: climate_entity_livingroom,
                ATTR_PRESET_MODE: PRESET_AWAY,
            },
            blocking=True,
        )


async def test_service_preset_mode_already_boost_valves(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service with boost preset for valves when already in boost mode."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_entrada = "climate.entrada_entrada"

    assert hass.states.get(climate_entity_entrada).state == "auto"
    assert (
        hass.states.get(climate_entity_entrada).attributes["preset_mode"]
        == "frost_guard"
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
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: climate_entity_entrada,
            ClimateServiceArgument.PRESET_MODE: PRESET_BOOST,
        },
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


async def test_service_preset_mode_boost_valves(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service with boost preset for valves."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_entrada = "climate.entrada_entrada"

    # Test service setting the preset mode to "boost"
    assert hass.states.get(climate_entity_entrada).state == "auto"
    assert hass.states.get(climate_entity_entrada).attributes["temperature"] == 7

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: climate_entity_entrada,
            ClimateServiceArgument.PRESET_MODE: PRESET_BOOST,
        },
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


async def test_service_preset_mode_invalid(
    hass: HomeAssistant, config_entry, caplog: pytest.LogCaptureFixture, netatmo_auth
) -> None:
    """Test service with invalid preset."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: "climate.cocina_cocina",
                ClimateServiceArgument.PRESET_MODE: "invalid",
            },
            blocking=True,
        )


async def test_valves_service_turn_off(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service turn off for valves."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_entrada = "climate.entrada_entrada"

    assert hass.states.get(climate_entity_entrada).attributes["hvac_modes"] == [
        "auto",
        "heat",
    ]

    # Test turning valve off
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.TURN_OFF,
        {TargetKey.ENTITY_ID: climate_entity_entrada},
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


async def test_valves_service_turn_on(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service turn on for valves."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_entrada = "climate.entrada_entrada"

    # Test turning valve on
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.TURN_ON,
        {TargetKey.ENTITY_ID: climate_entity_entrada},
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


async def test_webhook_home_id_mismatch(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service turn on for valves."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_entrada = "climate.entrada_entrada"

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


async def test_thermostat_update_with_none_therm_setpoint_mode(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test thermostat setup when Netatmo returns no therm setpoint mode."""

    def set_none_therm_setpoint_mode(payload: dict[str, Any]) -> None:
        """Set the thermostat setpoint mode to None in the backend response."""
        home = payload.get("body", {}).get("home")
        if home is None:
            return

        for room in home.get("rooms", []):
            if room["id"] == "2746182631":
                room["therm_setpoint_mode"] = None

    async def fake_post(*args: Any, **kwargs: Any):
        """Return backend data with a missing thermostat setpoint mode."""
        kwargs["msg_callback"] = set_none_therm_setpoint_mode
        return await fake_post_request(hass, *args, **kwargs)

    with (
        selected_platforms([Platform.CLIMATE]),
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
    ):
        mock_auth.return_value.async_post_request.side_effect = fake_post
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_get_image.side_effect = fake_get_image
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.livingroom_livingroom")
    assert state is not None
    assert state.state == HVACMode.AUTO
    assert state.attributes["preset_mode"] == PRESET_SCHEDULE


@pytest.mark.parametrize(
    ("boiler_status", "cooler_status", "expected"),
    [
        (True, False, HVACAction.HEATING),
        (False, True, HVACAction.COOLING),
        (False, False, HVACAction.IDLE),
    ],
)
async def test_thermostat_hvac_action_boiler_and_cooler_status(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    boiler_status: bool,
    cooler_status: bool,
    expected: HVACAction,
) -> None:
    """Test the hvac action of a Smarther reporting boiler and cooler status."""

    def set_smarther_status(payload: dict[str, Any]) -> None:
        """Set the Smarther boiler and cooler status in the backend response."""
        home = payload.get("body", {}).get("home")
        if home is None:
            return

        for module in home.get("modules", []):
            if module["id"] == "10:20:30:bd:b8:1e":
                module["boiler_status"] = boiler_status
                module["cooler_status"] = cooler_status

    async def fake_post(*args: Any, **kwargs: Any):
        """Return backend data with the given Smarther status."""
        kwargs["msg_callback"] = set_smarther_status
        return await fake_post_request(hass, *args, **kwargs)

    with (
        selected_platforms([Platform.CLIMATE]),
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
    ):
        mock_auth.return_value.async_post_request.side_effect = fake_post
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_get_image.side_effect = fake_get_image
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.corridor_corridor")
    assert state is not None
    assert state.attributes[ATTR_HVAC_ACTION] == expected


@pytest.mark.parametrize(
    ("setpoint_mode", "setpoint_temperature", "hvac_mode", "preset_mode"),
    [
        pytest.param("hg", 7, HVACMode.AUTO, PRESET_FROST_GUARD, id="frost_guard"),
        pytest.param("home", 23, HVACMode.AUTO, PRESET_SCHEDULE, id="schedule"),
        pytest.param("manual", 23.5, HVACMode.AUTO, "manual", id="manual"),
        pytest.param("max", None, HVACMode.HEAT, PRESET_BOOST, id="boost"),
    ],
)
async def test_thermostat_update_with_cooling_setpoint(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setpoint_mode: str,
    setpoint_temperature: float | None,
    hvac_mode: HVACMode,
    preset_mode: str,
) -> None:
    """Test thermostat setup for a home in cooling mode.

    A home whose temperature control mode is cooling gets cooling_setpoint_mode
    and cooling_setpoint_temperature from the backend, and no therm_setpoint_*
    fields at all.
    """

    def set_cooling_setpoint(payload: dict[str, Any]) -> None:
        """Replace the therm setpoint with a cooling one in the response."""
        # The inactive heating mode must not leak into a cooling room.
        for homesdata_home in payload.get("body", {}).get("homes", []):
            homesdata_home["therm_mode"] = "away"

        home = payload.get("body", {}).get("home")
        if home is None:
            return

        for room in home.get("rooms", []):
            if room["id"] == "2746182631":
                room.pop("therm_setpoint_mode", None)
                room.pop("therm_setpoint_temperature", None)
                room["cooling_setpoint_mode"] = setpoint_mode
                room["cooling_setpoint_temperature"] = setpoint_temperature

    async def fake_post(*args: Any, **kwargs: Any):
        """Return backend data for a home in cooling mode."""
        kwargs["msg_callback"] = set_cooling_setpoint
        return await fake_post_request(hass, *args, **kwargs)

    with (
        selected_platforms([Platform.CLIMATE]),
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
    ):
        mock_auth.return_value.async_post_request.side_effect = fake_post
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_get_image.side_effect = fake_get_image
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.livingroom_livingroom")
    assert state is not None
    assert state.state == hvac_mode
    assert state.attributes[ATTR_PRESET_MODE] == preset_mode
    assert state.attributes["temperature"] == setpoint_temperature


async def test_webhook_set_point(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test service turn on for valves."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    climate_entity_entrada = "climate.entrada_entrada"

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


class _FakeHomeMode:
    """Netatmo home mode as kept by the fake backend."""

    def __init__(self, mode: str | None) -> None:
        """Initialize the fake home mode."""
        self.mode = mode
        self.end_time: int | None = None

    @property
    def current(self) -> str | None:
        """Return the home mode, back to schedule once a timed mode has ended."""
        if self.end_time is not None and dt_util.utcnow().timestamp() >= self.end_time:
            return "schedule"
        return self.mode


async def _setup_with_room_in_home_mode(
    hass: HomeAssistant, config_entry: MockConfigEntry, home_therm_mode: str | None
) -> _FakeHomeMode:
    """Set up climate with the livingroom in "home" mode and a fake home mode."""
    home_mode = _FakeHomeMode(home_therm_mode)

    def set_modes(payload: dict[str, Any]) -> None:
        """Report the fake home mode in homesdata and "home" for the rooms."""
        body = payload.get("body", {})
        for home in body.get("homes", []):
            home["therm_mode"] = home_mode.current
        for room in body.get("home", {}).get("rooms", []):
            room["therm_setpoint_mode"] = "home"

    async def fake_post(*args: Any, **kwargs: Any):
        """Keep the home mode set through setthermmode, return modified data."""
        if kwargs.get("endpoint", "").endswith("setthermmode"):
            params = kwargs["params"]
            home_mode.mode = params["mode"]
            home_mode.end_time = int(params["endtime"]) if "endtime" in params else None
        kwargs["msg_callback"] = set_modes
        return await fake_post_request(hass, *args, **kwargs)

    with (
        selected_platforms([Platform.CLIMATE]),
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
    ):
        mock_auth.return_value.async_post_request.side_effect = fake_post
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_get_image.side_effect = fake_get_image
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return home_mode


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run enough polling cycles for the home status to be refreshed."""
    for _ in range(11):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run a single scan cycle, picking up forced updates only."""
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize(
    ("home_therm_mode", "expected_preset"),
    [
        pytest.param("away", PRESET_AWAY, id="away"),
        pytest.param("hg", PRESET_FROST_GUARD, id="frost_guard"),
        pytest.param("schedule", PRESET_SCHEDULE, id="schedule"),
        pytest.param(None, PRESET_SCHEDULE, id="missing"),
        pytest.param("unexpected", PRESET_SCHEDULE, id="unexpected"),
    ],
)
async def test_thermostat_preset_follows_home_therm_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    home_therm_mode: str | None,
    expected_preset: str,
) -> None:
    """Test the preset follows the home mode while the room reports "home"."""
    await _setup_with_room_in_home_mode(hass, config_entry, home_therm_mode)

    state = hass.states.get(CLIMATE_ENTITY_LIVINGROOM)
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_PRESET_MODE] == expected_preset


async def test_thermostat_preset_refreshes_home_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setting a preset refreshes the home mode without a webhook."""
    await _setup_with_room_in_home_mode(hass, config_entry, "schedule")
    assert (
        hass.states.get(CLIMATE_ENTITY_LIVINGROOM).attributes[ATTR_PRESET_MODE]
        == PRESET_SCHEDULE
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: CLIMATE_ENTITY_LIVINGROOM,
            ClimateServiceArgument.PRESET_MODE: PRESET_AWAY,
        },
        blocking=True,
    )
    await _tick(hass, freezer)
    assert (
        hass.states.get(CLIMATE_ENTITY_LIVINGROOM).attributes[ATTR_PRESET_MODE]
        == PRESET_AWAY
    )

    await _poll(hass, freezer)
    assert (
        hass.states.get(CLIMATE_ENTITY_LIVINGROOM).attributes[ATTR_PRESET_MODE]
        == PRESET_AWAY
    )


async def test_thermostat_webhook_therm_mode_refreshes_home_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a therm_mode webhook refreshes the home mode before the next poll."""
    home_mode = await _setup_with_room_in_home_mode(hass, config_entry, "schedule")
    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    # The mode was changed outside Home Assistant, e.g. in the Netatmo app.
    home_mode.mode = "away"
    await simulate_webhook(
        hass,
        webhook_id,
        {
            "event_type": "therm_mode",
            "home": {"id": "91763b24c43d3e344f424e8b", "therm_mode": "away"},
            "mode": "away",
            "previous_mode": "schedule",
            "push_type": "home_event_changed",
        },
    )
    assert (
        hass.states.get(CLIMATE_ENTITY_LIVINGROOM).attributes[ATTR_PRESET_MODE]
        == PRESET_AWAY
    )

    await _poll(hass, freezer)
    assert (
        hass.states.get(CLIMATE_ENTITY_LIVINGROOM).attributes[ATTR_PRESET_MODE]
        == PRESET_AWAY
    )


async def test_thermostat_webhook_schedule_ends_away_immediately(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a schedule therm_mode webhook is not overridden by the stale home mode."""
    home_mode = await _setup_with_room_in_home_mode(hass, config_entry, "away")
    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    assert (
        hass.states.get(CLIMATE_ENTITY_LIVINGROOM).attributes[ATTR_PRESET_MODE]
        == PRESET_AWAY
    )

    # Back to the schedule outside Home Assistant, e.g. in the Netatmo app.
    home_mode.mode = "schedule"
    await simulate_webhook(
        hass,
        webhook_id,
        {
            "event_type": "therm_mode",
            "home": {"id": "91763b24c43d3e344f424e8b", "therm_mode": "schedule"},
            "mode": "schedule",
            "previous_mode": "away",
            "push_type": "home_event_changed",
        },
    )
    assert (
        hass.states.get(CLIMATE_ENTITY_LIVINGROOM).attributes[ATTR_PRESET_MODE]
        == PRESET_SCHEDULE
    )

    await _tick(hass, freezer)
    assert (
        hass.states.get(CLIMATE_ENTITY_LIVINGROOM).attributes[ATTR_PRESET_MODE]
        == PRESET_SCHEDULE
    )


async def test_thermostat_timed_preset_refreshes_after_end(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the preset returns to schedule when a timed away ends, without webhook."""
    await _setup_with_room_in_home_mode(hass, config_entry, "schedule")

    await hass.services.async_call(
        DOMAIN,
        NetatmoService.SET_PRESET_MODE_WITH_END_DATETIME,
        {
            TargetKey.ENTITY_ID: CLIMATE_ENTITY_LIVINGROOM,
            ATTR_PRESET_MODE: PRESET_AWAY,
            NetatmoServiceArgument.END_DATETIME: (
                dt_util.utcnow() + timedelta(minutes=10)
            ).isoformat(),
        },
        blocking=True,
    )
    await _tick(hass, freezer)
    assert (
        hass.states.get(CLIMATE_ENTITY_LIVINGROOM).attributes[ATTR_PRESET_MODE]
        == PRESET_AWAY
    )

    # Well before the next scheduled topology refresh.
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _poll(hass, freezer)

    assert (
        hass.states.get(CLIMATE_ENTITY_LIVINGROOM).attributes[ATTR_PRESET_MODE]
        == PRESET_SCHEDULE
    )
