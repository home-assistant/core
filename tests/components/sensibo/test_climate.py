"""The test for the sensibo binary sensor platform."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

from pysensibo.model import SensiboData
import pytest
from voluptuous import MultipleInvalid

from homeassistant.components.climate import (
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
from homeassistant.components.sensibo.climate import (
    ATTR_AC_INTEGRATION,
    ATTR_GEO_INTEGRATION,
    ATTR_HIGH_TEMPERATURE_STATE,
    ATTR_HIGH_TEMPERATURE_THRESHOLD,
    ATTR_HORIZONTAL_SWING_MODE,
    ATTR_INDOOR_INTEGRATION,
    ATTR_LIGHT,
    ATTR_LOW_TEMPERATURE_STATE,
    ATTR_LOW_TEMPERATURE_THRESHOLD,
    ATTR_MINUTES,
    ATTR_OUTDOOR_INTEGRATION,
    ATTR_SENSITIVITY,
    ATTR_SMART_TYPE,
    ATTR_TARGET_TEMPERATURE,
    SERVICE_ASSUME_STATE,
    SERVICE_ENABLE_CLIMATE_REACT,
    SERVICE_ENABLE_PURE_BOOST,
    SERVICE_ENABLE_TIMER,
    SERVICE_FULL_STATE,
    _find_valid_target_temp,
)
from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    ATTR_STATE,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


async def test_climate_find_valid_targets() -> None:
    """Test function to return temperature from valid targets."""

    valid_targets = [10, 16, 17, 18, 19, 20]

    assert _find_valid_target_temp(7, valid_targets) == 10
    assert _find_valid_target_temp(10, valid_targets) == 10
    assert _find_valid_target_temp(11, valid_targets) == 16
    assert _find_valid_target_temp(15, valid_targets) == 16
    assert _find_valid_target_temp(16, valid_targets) == 16
    assert _find_valid_target_temp(18.5, valid_targets) == 19
    assert _find_valid_target_temp(20, valid_targets) == 20
    assert _find_valid_target_temp(25, valid_targets) == 20


async def test_climate(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    get_data: SensiboData,
    load_int: ConfigEntry,
) -> None:
    """Test the Sensibo climate."""

    state1 = hass.states.get("climate.hallway")
    state2 = hass.states.get("climate.kitchen")
    state3 = hass.states.get("climate.bedroom")

    assert state1.state == "heat"
    assert state1.attributes == {
        "hvac_modes": [
            "heat_cool",
            "cool",
            "dry",
            "fan_only",
            "heat",
            "off",
        ],
        "min_temp": 10,
        "max_temp": 20,
        "target_temp_step": 1,
        "fan_modes": ["low", "medium", "quiet"],
        "swing_modes": ["fixedmiddletop", "fixedtop", "stopped"],
        "current_temperature": 21.2,
        "temperature": 25,
        "current_humidity": 32.9,
        "fan_mode": "high",
        "swing_mode": "stopped",
        "friendly_name": "Hallway",
        "supported_features": 41,
    }

    assert state2.state == "off"

    assert not state3
    found_log = False
    logs = caplog.get_records("setup")
    for log in logs:
        if (
            log.message
            == "Device Bedroom not correctly registered with Sensibo cloud. Skipping device"
        ):
            found_log = True
            break

    assert found_log


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
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
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
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
    ), pytest.raises(HomeAssistantError):
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
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_SWING_MODE: "fixedtop"},
            blocking=True,
        )
        await hass.async_block_till_done()

    state2 = hass.states.get("climate.hallway")
    assert state2.attributes["swing_mode"] == "fixedtop"

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
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
    ), pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_SWING_MODE: "fixedtop"},
            blocking=True,
        )
    await hass.async_block_till_done()

    state3 = hass.states.get("climate.hallway")
    assert state3.attributes["swing_mode"] == "fixedtop"


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
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
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
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
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
    assert state2.attributes["temperature"] == 16

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
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

    state2 = hass.states.get("climate.hallway")
    assert state2.attributes["temperature"] == 19

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
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
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
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
    ), pytest.raises(MultipleInvalid):
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
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ), pytest.raises(HomeAssistantError):
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
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("climate.hallway")
    assert state1.attributes["temperature"] == 25

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
    ), pytest.raises(ValueError):
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
            dt_util.utcnow() + timedelta(minutes=5),
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
            dt_util.utcnow() + timedelta(minutes=5),
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
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("climate.hallway")
    assert state1.state == "heat"

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
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
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
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
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("climate.hallway")
    assert state1.state == "heat"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Error", "failureReason": "Did not work"}},
    ), pytest.raises(HomeAssistantError):
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
            dt_util.utcnow() + timedelta(minutes=5),
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


async def test_climate_no_fan_no_swing(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate fan service."""

    state = hass.states.get("climate.hallway")
    assert state.attributes["fan_mode"] == "high"
    assert state.attributes["swing_mode"] == "stopped"

    monkeypatch.setattr(get_data.parsed["ABC999111"], "fan_mode", None)
    monkeypatch.setattr(get_data.parsed["ABC999111"], "swing_mode", None)
    monkeypatch.setattr(get_data.parsed["ABC999111"], "fan_modes", None)
    monkeypatch.setattr(get_data.parsed["ABC999111"], "swing_modes", None)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state = hass.states.get("climate.hallway")
    assert state.attributes["fan_mode"] is None
    assert state.attributes["swing_mode"] is None
    assert state.attributes["fan_modes"] is None
    assert state.attributes["swing_modes"] is None


async def test_climate_set_timer(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate Set Timer service."""

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state_climate = hass.states.get("climate.hallway")
    assert hass.states.get("sensor.hallway_timer_end_time").state == STATE_UNKNOWN

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_timer",
        return_value={"status": "failure"},
    ), pytest.raises(
        MultipleInvalid
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_TIMER,
            {
                ATTR_ENTITY_ID: state_climate.entity_id,
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_timer",
        return_value={"status": "failure"},
    ), pytest.raises(
        HomeAssistantError
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_TIMER,
            {
                ATTR_ENTITY_ID: state_climate.entity_id,
                ATTR_MINUTES: 30,
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_timer",
        return_value={"status": "success", "result": {"id": "SzTGE4oZ4D"}},
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_TIMER,
            {
                ATTR_ENTITY_ID: state_climate.entity_id,
                ATTR_MINUTES: 30,
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    monkeypatch.setattr(get_data.parsed["ABC999111"], "timer_on", True)
    monkeypatch.setattr(get_data.parsed["ABC999111"], "timer_id", "SzTGE4oZ4D")
    monkeypatch.setattr(get_data.parsed["ABC999111"], "timer_state_on", False)
    monkeypatch.setattr(
        get_data.parsed["ABC999111"],
        "timer_time",
        datetime(2022, 6, 6, 12, 00, 00, tzinfo=dt_util.UTC),
    )

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.hallway_timer_end_time").state
        == "2022-06-06T12:00:00+00:00"
    )


async def test_climate_pure_boost(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate assumed state service."""

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state_climate = hass.states.get("climate.kitchen")
    state2 = hass.states.get("switch.kitchen_pure_boost")
    assert state2.state == "off"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_pureboost",
    ), pytest.raises(
        MultipleInvalid
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_PURE_BOOST,
            {
                ATTR_ENTITY_ID: state_climate.entity_id,
                ATTR_INDOOR_INTEGRATION: True,
                ATTR_OUTDOOR_INTEGRATION: True,
                ATTR_SENSITIVITY: "Sensitive",
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_pureboost",
        return_value={
            "status": "success",
            "result": {
                "enabled": True,
                "sensitivity": "S",
                "measurements_integration": True,
                "ac_integration": False,
                "geo_integration": False,
                "prime_integration": True,
            },
        },
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_PURE_BOOST,
            {
                ATTR_ENTITY_ID: state_climate.entity_id,
                ATTR_AC_INTEGRATION: False,
                ATTR_GEO_INTEGRATION: False,
                ATTR_INDOOR_INTEGRATION: True,
                ATTR_OUTDOOR_INTEGRATION: True,
                ATTR_SENSITIVITY: "Sensitive",
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    monkeypatch.setattr(get_data.parsed["AAZZAAZZ"], "pure_boost_enabled", True)
    monkeypatch.setattr(get_data.parsed["AAZZAAZZ"], "pure_sensitivity", "s")
    monkeypatch.setattr(get_data.parsed["AAZZAAZZ"], "pure_measure_integration", True)
    monkeypatch.setattr(get_data.parsed["AAZZAAZZ"], "pure_prime_integration", True)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("switch.kitchen_pure_boost")
    state2 = hass.states.get(
        "binary_sensor.kitchen_pure_boost_linked_with_indoor_air_quality"
    )
    state3 = hass.states.get(
        "binary_sensor.kitchen_pure_boost_linked_with_outdoor_air_quality"
    )
    state4 = hass.states.get("sensor.kitchen_pure_sensitivity")
    assert state1.state == "on"
    assert state2.state == "on"
    assert state3.state == "on"
    assert state4.state == "s"


async def test_climate_climate_react(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate react custom service."""

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state_climate = hass.states.get("climate.hallway")

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_climate_react",
    ), pytest.raises(
        MultipleInvalid
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_PURE_BOOST,
            {
                ATTR_ENTITY_ID: state_climate.entity_id,
                ATTR_LOW_TEMPERATURE_THRESHOLD: 0.2,
                ATTR_HIGH_TEMPERATURE_THRESHOLD: 30.3,
                ATTR_SMART_TYPE: "temperature",
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_climate_react",
        return_value={
            "status": "success",
            "result": {
                "enabled": True,
                "deviceUid": "ABC999111",
                "highTemperatureState": {
                    "on": True,
                    "targetTemperature": 15,
                    "temperatureUnit": "C",
                    "mode": "cool",
                    "fanLevel": "high",
                    "swing": "stopped",
                    "horizontalSwing": "stopped",
                    "light": "on",
                },
                "highTemperatureThreshold": 30.5,
                "lowTemperatureState": {
                    "on": True,
                    "targetTemperature": 25,
                    "temperatureUnit": "C",
                    "mode": "heat",
                    "fanLevel": "low",
                    "swing": "stopped",
                    "horizontalSwing": "stopped",
                    "light": "on",
                },
                "lowTemperatureThreshold": 5.5,
                "type": "temperature",
            },
        },
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_CLIMATE_REACT,
            {
                ATTR_ENTITY_ID: state_climate.entity_id,
                ATTR_LOW_TEMPERATURE_THRESHOLD: 5.5,
                ATTR_HIGH_TEMPERATURE_THRESHOLD: 30.5,
                ATTR_LOW_TEMPERATURE_STATE: {
                    "on": True,
                    "targetTemperature": 25,
                    "temperatureUnit": "C",
                    "mode": "heat",
                    "fanLevel": "low",
                    "swing": "stopped",
                    "horizontalSwing": "stopped",
                    "light": "on",
                },
                ATTR_HIGH_TEMPERATURE_STATE: {
                    "on": True,
                    "targetTemperature": 15,
                    "temperatureUnit": "C",
                    "mode": "cool",
                    "fanLevel": "high",
                    "swing": "stopped",
                    "horizontalSwing": "stopped",
                    "light": "on",
                },
                ATTR_SMART_TYPE: "temperature",
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    monkeypatch.setattr(get_data.parsed["ABC999111"], "smart_on", True)
    monkeypatch.setattr(get_data.parsed["ABC999111"], "smart_type", "temperature")
    monkeypatch.setattr(get_data.parsed["ABC999111"], "smart_low_temp_threshold", 5.5)
    monkeypatch.setattr(get_data.parsed["ABC999111"], "smart_high_temp_threshold", 30.5)
    monkeypatch.setattr(
        get_data.parsed["ABC999111"],
        "smart_low_state",
        {
            "on": True,
            "targetTemperature": 25,
            "temperatureUnit": "C",
            "mode": "heat",
            "fanLevel": "low",
            "swing": "stopped",
            "horizontalSwing": "stopped",
            "light": "on",
        },
    )
    monkeypatch.setattr(
        get_data.parsed["ABC999111"],
        "smart_high_state",
        {
            "on": True,
            "targetTemperature": 15,
            "temperatureUnit": "C",
            "mode": "cool",
            "fanLevel": "high",
            "swing": "stopped",
            "horizontalSwing": "stopped",
            "light": "on",
        },
    )

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("switch.hallway_climate_react")
    state2 = hass.states.get("sensor.hallway_climate_react_low_temperature_threshold")
    state3 = hass.states.get("sensor.hallway_climate_react_high_temperature_threshold")
    state4 = hass.states.get("sensor.hallway_climate_react_type")
    assert state1.state == "on"
    assert state2.state == "5.5"
    assert state3.state == "30.5"
    assert state4.state == "temperature"


async def test_climate_climate_react_fahrenheit(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate react custom service with fahrenheit."""

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state_climate = hass.states.get("climate.hallway")

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_climate_react",
        return_value={
            "status": "success",
            "result": {
                "enabled": True,
                "deviceUid": "ABC999111",
                "highTemperatureState": {
                    "on": True,
                    "targetTemperature": 65,
                    "temperatureUnit": "F",
                    "mode": "cool",
                    "fanLevel": "high",
                    "swing": "stopped",
                    "horizontalSwing": "stopped",
                    "light": "on",
                },
                "highTemperatureThreshold": 77,
                "lowTemperatureState": {
                    "on": True,
                    "targetTemperature": 85,
                    "temperatureUnit": "F",
                    "mode": "heat",
                    "fanLevel": "low",
                    "swing": "stopped",
                    "horizontalSwing": "stopped",
                    "light": "on",
                },
                "lowTemperatureThreshold": 32,
                "type": "temperature",
            },
        },
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_CLIMATE_REACT,
            {
                ATTR_ENTITY_ID: state_climate.entity_id,
                ATTR_LOW_TEMPERATURE_THRESHOLD: 32.0,
                ATTR_HIGH_TEMPERATURE_THRESHOLD: 77.0,
                ATTR_LOW_TEMPERATURE_STATE: {
                    "on": True,
                    "targetTemperature": 85,
                    "temperatureUnit": "F",
                    "mode": "heat",
                    "fanLevel": "low",
                    "swing": "stopped",
                    "horizontalSwing": "stopped",
                    "light": "on",
                },
                ATTR_HIGH_TEMPERATURE_STATE: {
                    "on": True,
                    "targetTemperature": 65,
                    "temperatureUnit": "F",
                    "mode": "cool",
                    "fanLevel": "high",
                    "swing": "stopped",
                    "horizontalSwing": "stopped",
                    "light": "on",
                },
                ATTR_SMART_TYPE: "temperature",
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    monkeypatch.setattr(get_data.parsed["ABC999111"], "smart_on", True)
    monkeypatch.setattr(get_data.parsed["ABC999111"], "smart_type", "temperature")
    monkeypatch.setattr(get_data.parsed["ABC999111"], "smart_low_temp_threshold", 0)
    monkeypatch.setattr(get_data.parsed["ABC999111"], "smart_high_temp_threshold", 25)
    monkeypatch.setattr(
        get_data.parsed["ABC999111"],
        "smart_low_state",
        {
            "on": True,
            "targetTemperature": 85,
            "temperatureUnit": "F",
            "mode": "heat",
            "fanLevel": "low",
            "swing": "stopped",
            "horizontalSwing": "stopped",
            "light": "on",
        },
    )
    monkeypatch.setattr(
        get_data.parsed["ABC999111"],
        "smart_high_state",
        {
            "on": True,
            "targetTemperature": 65,
            "temperatureUnit": "F",
            "mode": "cool",
            "fanLevel": "high",
            "swing": "stopped",
            "horizontalSwing": "stopped",
            "light": "on",
        },
    )

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("switch.hallway_climate_react")
    state2 = hass.states.get("sensor.hallway_climate_react_low_temperature_threshold")
    state3 = hass.states.get("sensor.hallway_climate_react_high_temperature_threshold")
    state4 = hass.states.get("sensor.hallway_climate_react_type")
    assert state1.state == "on"
    assert state2.state == "0"
    assert state3.state == "25"
    assert state4.state == "temperature"


async def test_climate_full_ac_state(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate Full AC state service."""

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state_climate = hass.states.get("climate.hallway")
    assert state_climate.state == "heat"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_states",
    ), pytest.raises(
        MultipleInvalid
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_FULL_STATE,
            {
                ATTR_ENTITY_ID: state_climate.entity_id,
                ATTR_TARGET_TEMPERATURE: 22,
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_states",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_FULL_STATE,
            {
                ATTR_ENTITY_ID: state_climate.entity_id,
                ATTR_MODE: "cool",
                ATTR_TARGET_TEMPERATURE: 22,
                ATTR_FAN_MODE: "high",
                ATTR_SWING_MODE: "stopped",
                ATTR_HORIZONTAL_SWING_MODE: "stopped",
                ATTR_LIGHT: "on",
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    monkeypatch.setattr(get_data.parsed["ABC999111"], "hvac_mode", "cool")
    monkeypatch.setattr(get_data.parsed["ABC999111"], "device_on", True)
    monkeypatch.setattr(get_data.parsed["ABC999111"], "target_temp", 22)
    monkeypatch.setattr(get_data.parsed["ABC999111"], "fan_mode", "high")
    monkeypatch.setattr(get_data.parsed["ABC999111"], "swing_mode", "stopped")
    monkeypatch.setattr(
        get_data.parsed["ABC999111"], "horizontal_swing_mode", "stopped"
    )
    monkeypatch.setattr(get_data.parsed["ABC999111"], "light_mode", "on")

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state = hass.states.get("climate.hallway")

    assert state.state == "cool"
    assert state.attributes["temperature"] == 22


async def test_climate_fan_mode_and_swing_mode_not_supported(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate fan_mode and swing_mode not supported is raising error."""

    state1 = hass.states.get("climate.hallway")
    assert state1.attributes["fan_mode"] == "high"
    assert state1.attributes["swing_mode"] == "stopped"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
    ), pytest.raises(
        HomeAssistantError,
        match="Climate swing mode faulty_swing_mode is not supported by the integration, please open an issue",
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_SWING_MODE: "faulty_swing_mode"},
            blocking=True,
        )

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
    ), pytest.raises(
        HomeAssistantError,
        match="Climate fan mode faulty_fan_mode is not supported by the integration, please open an issue",
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_FAN_MODE: "faulty_fan_mode"},
            blocking=True,
        )

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state2 = hass.states.get("climate.hallway")
    assert state2.attributes["fan_mode"] == "high"
    assert state2.attributes["swing_mode"] == "stopped"
