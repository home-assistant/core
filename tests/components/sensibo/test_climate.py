"""The test for the sensibo binary sensor platform."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from pysensibo.model import SensiboData
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_STATE,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt

from tests.common import async_fire_time_changed


async def test_climate(
    hass: HomeAssistant, load_int: ConfigEntry, get_data: SensiboData
) -> None:
    """Test the Sensibo climate."""

    state1 = hass.states.get("climate.hallway")
    state2 = hass.states.get("climate.kitchen")

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
        "min_temp": 17,
        "max_temp": 20,
        "target_temp_step": 1,
        "fan_modes": ["quiet", "low", "medium"],
        "swing_modes": [
            "stopped",
            "fixedTop",
            "fixedMiddleTop",
        ],
        "current_temperature": 21.2,
        "temperature": 25,
        "current_humidity": 32.9,
        "fan_mode": "high",
        "swing_mode": "stopped",
        "friendly_name": "Hallway",
        "supported_features": 41,
    }

    assert state2.state == "off"


async def test_climate_fan(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate fan service."""

    state1 = hass.states.get("climate.hallway")
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

    state2 = hass.states.get("climate.hallway")
    assert state2.attributes["fan_mode"] == "low"

    monkeypatch.setattr(
        get_data.parsed["ABC999111"],
        "active_features",
        [
            "timestamp",
            "on",
            "mode",
            "swing",
            "targetTemperature",
            "horizontalSwing",
            "light",
        ],
    )
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_FAN_MODE,
                {ATTR_ENTITY_ID: state1.entity_id, ATTR_FAN_MODE: "low"},
                blocking=True,
            )
    await hass.async_block_till_done()

    state3 = hass.states.get("climate.hallway")
    assert state3.attributes["fan_mode"] == "low"


async def test_climate_swing(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate swing service."""

    state1 = hass.states.get("climate.hallway")
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

    state2 = hass.states.get("climate.hallway")
    assert state2.attributes["swing_mode"] == "fixedTop"

    monkeypatch.setattr(
        get_data.parsed["ABC999111"],
        "active_features",
        [
            "timestamp",
            "on",
            "mode",
            "targetTemperature",
            "horizontalSwing",
            "light",
        ],
    )
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_SWING_MODE,
                {ATTR_ENTITY_ID: state1.entity_id, ATTR_SWING_MODE: "fixedTop"},
                blocking=True,
            )
    await hass.async_block_till_done()

    state3 = hass.states.get("climate.hallway")
    assert state3.attributes["swing_mode"] == "fixedTop"


async def test_climate_temperatures(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate temperature service."""

    state1 = hass.states.get("climate.hallway")
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

    state2 = hass.states.get("climate.hallway")
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

    state2 = hass.states.get("climate.hallway")
    assert state2.attributes["temperature"] == 17

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        with pytest.raises(ValueError):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_TEMPERATURE,
                {ATTR_ENTITY_ID: state1.entity_id, ATTR_TEMPERATURE: 18.5},
                blocking=True,
            )
    await hass.async_block_till_done()

    state2 = hass.states.get("climate.hallway")
    assert state2.attributes["temperature"] == 17

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

    state2 = hass.states.get("climate.hallway")
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

    state2 = hass.states.get("climate.hallway")
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

    state2 = hass.states.get("climate.hallway")
    assert state2.attributes["temperature"] == 20

    monkeypatch.setattr(
        get_data.parsed["ABC999111"],
        "active_features",
        [
            "timestamp",
            "on",
            "mode",
            "swing",
            "horizontalSwing",
            "light",
        ],
    )
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

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

    state2 = hass.states.get("climate.hallway")
    assert state2.attributes["temperature"] == 20


async def test_climate_temperature_is_none(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate temperature service no temperature provided."""

    monkeypatch.setattr(
        get_data.parsed["ABC999111"],
        "active_features",
        [
            "timestamp",
            "on",
            "mode",
            "fanLevel",
            "targetTemperature",
            "swing",
            "horizontalSwing",
            "light",
        ],
    )
    monkeypatch.setattr(
        get_data.parsed["ABC999111"],
        "target_temp",
        25,
    )
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("climate.hallway")
    assert state1.attributes["temperature"] == 25

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
    ):
        with pytest.raises(ValueError):
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

    state2 = hass.states.get("climate.hallway")
    assert state2.attributes["temperature"] == 25


async def test_climate_hvac_mode(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate hvac mode service."""

    monkeypatch.setattr(
        get_data.parsed["ABC999111"],
        "active_features",
        [
            "timestamp",
            "on",
            "mode",
            "fanLevel",
            "targetTemperature",
            "swing",
            "horizontalSwing",
            "light",
        ],
    )
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("climate.hallway")
    assert state1.state == "heat"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=get_data,
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

    state2 = hass.states.get("climate.hallway")
    assert state2.state == "off"

    monkeypatch.setattr(get_data.parsed["ABC999111"], "device_on", False)
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=get_data,
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

    state2 = hass.states.get("climate.hallway")
    assert state2.state == "heat"


async def test_climate_on_off(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate on/off service."""

    monkeypatch.setattr(get_data.parsed["ABC999111"], "hvac_mode", "heat")
    monkeypatch.setattr(get_data.parsed["ABC999111"], "device_on", True)
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("climate.hallway")
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

    state2 = hass.states.get("climate.hallway")
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

    state2 = hass.states.get("climate.hallway")
    assert state2.state == "heat"


async def test_climate_service_failed(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate service failed."""

    monkeypatch.setattr(get_data.parsed["ABC999111"], "hvac_mode", "heat")
    monkeypatch.setattr(get_data.parsed["ABC999111"], "device_on", True)
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("climate.hallway")
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

    state2 = hass.states.get("climate.hallway")
    assert state2.state == "heat"


async def test_climate_assumed_state(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate assumed state service."""

    monkeypatch.setattr(get_data.parsed["ABC999111"], "hvac_mode", "heat")
    monkeypatch.setattr(get_data.parsed["ABC999111"], "device_on", True)
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("climate.hallway")
    assert state1.state == "heat"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=get_data,
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

    state2 = hass.states.get("climate.hallway")
    assert state2.state == "off"
