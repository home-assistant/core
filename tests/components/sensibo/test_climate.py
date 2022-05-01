"""The test for the sensibo binary sensor platform."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from voluptuous import MultipleInvalid

from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.sensibo.climate import SERVICE_ASSUME_STATE
from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.components.sensibo.coordinator import SensiboDataUpdateCoordinator
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_STATE,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import DATA_FROM_API, init_integration


async def test_climate(hass: HomeAssistant) -> None:
    """Test the Sensibo climate."""
    await init_integration(hass, name=["Clima1", "Pure1"], entry_id="clima1")

    state1 = hass.states.get("climate.clima1")
    state2 = hass.states.get("climate.pure1")

    assert state1.state == "heat"
    assert state1.attributes == {
        "hvac_modes": [
            "cool",
            "heat",
            "dry",
            "heat_cool",
            "fan_only",
            "off",
        ],
        "min_temp": 18,
        "max_temp": 20,
        "target_temp_step": 1,
        "fan_modes": ["quiet", "low", "medium"],
        "swing_modes": [
            "stopped",
            "fixedTop",
            "fixedMiddleTop",
        ],
        "current_temperature": 22.4,
        "temperature": 25,
        "current_humidity": 38,
        "fan_mode": "high",
        "swing_mode": "stopped",
        "friendly_name": "Clima1",
        "supported_features": 41,
    }

    assert state2.state == "off"


async def test_climate_fan(hass: HomeAssistant) -> None:
    """Test the Sensibo climate fan service."""
    entry = await init_integration(hass, name=["Clima2", "Pure2"], entry_id="clima2")

    state1 = hass.states.get("climate.clima2")
    assert state1.attributes["fan_mode"] == "high"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_FAN_MODE: "low"},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima2")
    assert state2.attributes["fan_mode"] == "low"

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.data.parsed["ABC999111"].active_features = [
        "timestamp",
        "on",
        "mode",
        "swing",
        "horizontalSwing",
        "light",
    ]

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_FAN_MODE,
                {ATTR_ENTITY_ID: state1.entity_id, ATTR_FAN_MODE: "low"},
                blocking=True,
            )
    await hass.async_block_till_done()

    state3 = hass.states.get("climate.clima2")
    assert state3.attributes["fan_mode"] == "low"


async def test_climate_swing(hass: HomeAssistant) -> None:
    """Test the Sensibo climate swing service."""
    entry = await init_integration(hass, name=["Clima3", "Pure3"], entry_id="clima3")

    state1 = hass.states.get("climate.clima3")
    assert state1.attributes["swing_mode"] == "stopped"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_SWING_MODE: "fixedTop"},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima3")
    assert state2.attributes["swing_mode"] == "fixedTop"

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.data.parsed["ABC999111"].active_features = [
        "timestamp",
        "on",
        "mode",
        "horizontalSwing",
        "light",
    ]

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_SWING_MODE,
                {ATTR_ENTITY_ID: state1.entity_id, ATTR_SWING_MODE: "fixedTop"},
                blocking=True,
            )
    await hass.async_block_till_done()

    state3 = hass.states.get("climate.clima3")
    assert state3.attributes["swing_mode"] == "fixedTop"


async def test_climate_temperature(hass: HomeAssistant) -> None:
    """Test the Sensibo climate temperature service."""
    entry = await init_integration(hass, name=["Clima4", "Pure4"], entry_id="clima4")

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.data.parsed["ABC999111"].active_features = [
        "timestamp",
        "on",
        "mode",
        "fanLevel",
        "targetTemperature",
        "swing",
        "horizontalSwing",
        "light",
    ]

    state1 = hass.states.get("climate.clima4")
    assert state1.attributes["temperature"] == 25

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_TEMPERATURE: 20},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima4")
    assert state2.attributes["temperature"] == 20

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_TEMPERATURE: 15},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima4")
    assert state2.attributes["temperature"] == 18

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_TEMPERATURE: 18.5},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima4")
    assert state2.attributes["temperature"] == 18

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_TEMPERATURE: 24},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima4")
    assert state2.attributes["temperature"] == 20

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_TEMPERATURE: 20},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima4")
    assert state2.attributes["temperature"] == 20

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        with pytest.raises(MultipleInvalid):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_TEMPERATURE,
                {ATTR_ENTITY_ID: state1.entity_id},
                blocking=True,
            )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima4")
    assert state2.attributes["temperature"] == 20

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.data.parsed["ABC999111"].active_features = [
        "timestamp",
        "on",
        "mode",
        "fanLevel",
        "swing",
        "horizontalSwing",
        "light",
    ]

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_TEMPERATURE,
                {ATTR_ENTITY_ID: state1.entity_id, ATTR_TEMPERATURE: 20},
                blocking=True,
            )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima4")
    assert state2.attributes["temperature"] == 20


async def test_climate_temperature_is_none(hass: HomeAssistant) -> None:
    """Test the Sensibo climate temperature service no temperature provided."""
    entry = await init_integration(hass, name=["Clima5", "Pure5"], entry_id="clima5")

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.data.parsed["ABC999111"].active_features = [
        "timestamp",
        "on",
        "mode",
        "fanLevel",
        "targetTemperature",
        "swing",
        "horizontalSwing",
        "light",
    ]

    state1 = hass.states.get("climate.clima5")
    assert state1.attributes["temperature"] == 20

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: state1.entity_id,
                ATTR_TARGET_TEMP_HIGH: 30,
                ATTR_TARGET_TEMP_LOW: 20,
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima5")
    assert state2.attributes["temperature"] == 20


async def test_climate_hvac_mode(hass: HomeAssistant) -> None:
    """Test the Sensibo climate hvac mode service."""
    entry = await init_integration(hass, name=["Clima6", "Pure6"], entry_id="clima6")

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.data.parsed["ABC999111"].active_features = [
        "timestamp",
        "on",
        "mode",
        "fanLevel",
        "targetTemperature",
        "swing",
        "horizontalSwing",
        "light",
    ]

    state1 = hass.states.get("climate.clima6")
    assert state1.state == "heat"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_HVAC_MODE: "off"},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima6")
    assert state2.state == "off"

    coordinator.data.parsed["ABC999111"].device_on = False

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_HVAC_MODE: "heat"},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima6")
    assert state2.state == "heat"


async def test_climate_on_off(hass: HomeAssistant) -> None:
    """Test the Sensibo climate on/off service."""
    await init_integration(hass, name=["Clima7", "Pure7"], entry_id="clima7")

    state1 = hass.states.get("climate.clima7")
    assert state1.state == "heat"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: state1.entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima7")
    assert state2.state == "off"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: state1.entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima7")
    assert state2.state == "heat"


async def test_climate_service_failed(hass: HomeAssistant) -> None:
    """Test the Sensibo climate service failed."""
    await init_integration(hass, name=["Clima8", "Pure8"], entry_id="clima8")

    state1 = hass.states.get("climate.clima8")
    assert state1.state == "heat"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Error", "failureReason": "Did not work"}},
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: state1.entity_id},
                blocking=True,
            )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima8")
    assert state2.state == "heat"


async def test_climate_assumed_state(hass: HomeAssistant) -> None:
    """Test the Sensibo climate assumed state service."""
    await init_integration(hass, name=["Clima9", "Pure9"], entry_id="clima9")

    state1 = hass.states.get("climate.clima9")
    assert state1.state == "heat"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ASSUME_STATE,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_STATE: "off"},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.clima9")
    assert state2.state == "off"
