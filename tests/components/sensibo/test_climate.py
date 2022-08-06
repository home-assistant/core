"""The test for the sensibo binary sensor platform."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

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
from homeassistant.components.sensibo.climate import (
    ATTR_AC_INTEGRATION,
    ATTR_GEO_INTEGRATION,
    ATTR_INDOOR_INTEGRATION,
    ATTR_MINUTES,
    ATTR_OUTDOOR_INTEGRATION,
    ATTR_SENSITIVITY,
    SERVICE_ASSUME_STATE,
    SERVICE_ENABLE_PURE_BOOST,
    SERVICE_ENABLE_TIMER,
    _find_valid_target_temp,
)
from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_STATE,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt

from tests.common import async_fire_time_changed


async def test_climate_find_valid_targets():
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
        "min_temp": 10,
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
    assert state2.attributes["temperature"] == 16

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

    state2 = hass.states.get("climate.hallway")
    assert state2.attributes["temperature"] == 19

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
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state = hass.states.get("climate.hallway")
    assert state.attributes["fan_mode"] is None
    assert state.attributes["swing_mode"] is None
    assert state.attributes["fan_modes"] is None
    assert state.attributes["swing_modes"] is None


async def test_climate_set_timer(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: AsyncMock,
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
            dt.utcnow() + timedelta(minutes=5),
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
    ):
        with pytest.raises(MultipleInvalid):
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
    ):
        with pytest.raises(HomeAssistantError):
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
        datetime(2022, 6, 6, 12, 00, 00, tzinfo=dt.UTC),
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

    assert (
        hass.states.get("sensor.hallway_timer_end_time").state
        == "2022-06-06T12:00:00+00:00"
    )


async def test_climate_pure_boost(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: AsyncMock,
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
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state_climate = hass.states.get("climate.kitchen")
    state2 = hass.states.get("switch.kitchen_pure_boost")
    assert state2.state == "off"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_pureboost",
    ):
        with pytest.raises(MultipleInvalid):
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
            dt.utcnow() + timedelta(minutes=5),
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
