"""The test for the sensibo climate platform."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from voluptuous import MultipleInvalid

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
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
    SERVICE_GET_DEVICE_CAPABILITIES,
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
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed, snapshot_platform


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


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.CLIMATE]],
)
async def test_climate(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    load_int: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Sensibo climate."""

    await snapshot_platform(hass, entity_registry, snapshot, load_int.entry_id)

    logs = caplog.get_records("setup")

    assert "Device Bedroom not correctly registered with remote on Sensibo cloud." in [
        log.message for log in logs
    ]


async def test_climate_fan(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate fan service."""

    state = hass.states.get("climate.hallway")
    assert state.attributes["fan_mode"] == "high"

    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].fan_modes = [
        "quiet",
        "low",
        "medium",
        "not_in_ha",
    ]
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].fan_modes_translated = {
        "low": "low",
        "medium": "medium",
        "quiet": "quiet",
        "not_in_ha": "not_in_ha",
    }

    with pytest.raises(
        HomeAssistantError,
        match="Climate fan mode not_in_ha is not supported by the integration",
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_FAN_MODE: "not_in_ha"},
            blocking=True,
        )

    mock_client.async_set_ac_state_property.return_value = {
        "result": {"status": "Success"}
    }

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_FAN_MODE: "low"},
        blocking=True,
    )

    state = hass.states.get("climate.hallway")
    assert state.attributes["fan_mode"] == "low"

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].active_features = [
        "timestamp",
        "on",
        "mode",
        "swing",
        "targetTemperature",
        "horizontalSwing",
        "light",
    ]

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError, match="service_not_supported"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_FAN_MODE: "low"},
            blocking=True,
        )

    state = hass.states.get("climate.hallway")
    assert "fan_mode" not in state.attributes


async def test_climate_swing(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate swing service."""

    state = hass.states.get("climate.hallway")
    assert state.attributes["swing_mode"] == "stopped"

    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].swing_modes = [
        "stopped",
        "fixedtop",
        "fixedmiddletop",
        "not_in_ha",
    ]
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].swing_modes_translated = {
        "fixedmiddletop": "fixedMiddleTop",
        "fixedtop": "fixedTop",
        "stopped": "stopped",
        "not_in_ha": "not_in_ha",
    }

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    with pytest.raises(
        HomeAssistantError,
        match="Climate swing mode not_in_ha is not supported by the integration",
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_SWING_MODE: "not_in_ha"},
            blocking=True,
        )

    mock_client.async_set_ac_state_property.return_value = {
        "result": {"status": "Success"}
    }

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_SWING_MODE: "fixedtop"},
        blocking=True,
    )

    state = hass.states.get("climate.hallway")
    assert state.attributes["swing_mode"] == "fixedtop"

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].active_features = [
        "timestamp",
        "on",
        "mode",
        "targetTemperature",
        "horizontalSwing",
        "light",
    ]
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError, match="service_not_supported"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_SWING_MODE: "fixedtop"},
            blocking=True,
        )

    state = hass.states.get("climate.hallway")
    assert "swing_mode" not in state.attributes


async def test_climate_horizontal_swing(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate horizontal swing service."""

    state = hass.states.get("climate.hallway")
    assert state.attributes["swing_horizontal_mode"] == "stopped"

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].horizontal_swing_modes = [
        "stopped",
        "fixedleft",
        "fixedcenter",
        "fixedright",
        "not_in_ha",
    ]
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].swing_modes_translated = {
        "stopped": "stopped",
        "fixedleft": "fixedLeft",
        "fixedcenter": "fixedCenter",
        "fixedright": "fixedRight",
        "not_in_ha": "not_in_ha",
    }

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    with pytest.raises(
        HomeAssistantError,
        match="Climate horizontal swing mode not_in_ha is not supported by the integration",
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_SWING_HORIZONTAL_MODE: "not_in_ha"},
            blocking=True,
        )

    mock_client.async_set_ac_state_property.return_value = {
        "result": {"status": "Success"}
    }

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_HORIZONTAL_MODE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_SWING_HORIZONTAL_MODE: "fixedleft"},
        blocking=True,
    )

    state = hass.states.get("climate.hallway")
    assert state.attributes["swing_horizontal_mode"] == "fixedleft"

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].active_features = [
        "timestamp",
        "on",
        "mode",
        "targetTemperature",
        "swing",
        "light",
    ]

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError, match="service_not_supported"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            {
                ATTR_ENTITY_ID: state.entity_id,
                ATTR_SWING_HORIZONTAL_MODE: "fixedcenter",
            },
            blocking=True,
        )

    state = hass.states.get("climate.hallway")
    assert "swing_horizontal_mode" not in state.attributes


async def test_climate_temperatures(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate temperature service."""

    state = hass.states.get("climate.hallway")
    assert state.attributes["temperature"] == 25

    mock_client.async_set_ac_state_property.return_value = {
        "result": {"status": "Success"}
    }

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_TEMPERATURE: 20},
        blocking=True,
    )

    state = hass.states.get("climate.hallway")
    assert state.attributes["temperature"] == 20

    mock_client.async_set_ac_state_property.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_TEMPERATURE: 20},
        blocking=True,
    )
    assert not mock_client.async_set_ac_state_property.called

    mock_client.async_set_ac_state_property.return_value = {
        "result": {"status": "Success"}
    }

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_TEMPERATURE: 15},
        blocking=True,
    )

    state = hass.states.get("climate.hallway")
    assert state.attributes["temperature"] == 16

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_TEMPERATURE: 18.5},
        blocking=True,
    )

    state2 = hass.states.get("climate.hallway")
    assert state2.attributes["temperature"] == 19

    with pytest.raises(
        ServiceValidationError,
        match="Provided temperature 24.0 is not valid. Accepted range is 10 to 20",
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_TEMPERATURE: 24},
            blocking=True,
        )

    state = hass.states.get("climate.hallway")
    assert state.attributes["temperature"] == 19

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_TEMPERATURE: 20},
        blocking=True,
    )

    state = hass.states.get("climate.hallway")
    assert state.attributes["temperature"] == 20

    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: state.entity_id},
            blocking=True,
        )

    state = hass.states.get("climate.hallway")
    assert state.attributes["temperature"] == 20

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].active_features = [
        "timestamp",
        "on",
        "mode",
        "swing",
        "horizontalSwing",
        "light",
    ]

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError, match="service_not_supported"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_TEMPERATURE: 20},
            blocking=True,
        )

    state = hass.states.get("climate.hallway")
    assert "temperature" not in state.attributes


async def test_climate_temperature_is_none(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate temperature service no temperature provided."""

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].active_features = [
        "timestamp",
        "on",
        "mode",
        "fanLevel",
        "targetTemperature",
        "swing",
        "horizontalSwing",
        "light",
    ]
    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].target_temp = 25

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("climate.hallway")
    assert state.attributes["temperature"] == 25

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: state.entity_id,
                ATTR_TARGET_TEMP_HIGH: 30,
                ATTR_TARGET_TEMP_LOW: 20,
            },
            blocking=True,
        )

    state = hass.states.get("climate.hallway")
    assert state.attributes["temperature"] == 25


async def test_climate_hvac_mode(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate hvac mode service."""

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].active_features = [
        "timestamp",
        "on",
        "mode",
        "fanLevel",
        "targetTemperature",
        "swing",
        "horizontalSwing",
        "light",
    ]

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("climate.hallway")
    assert state.state == HVACMode.HEAT

    mock_client.async_set_ac_state_property.return_value = {
        "result": {"status": "Success"}
    }

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_HVAC_MODE: "off"},
        blocking=True,
    )

    state = hass.states.get("climate.hallway")
    assert state.state == HVACMode.OFF

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].device_on = False

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_HVAC_MODE: "heat"},
        blocking=True,
    )

    state = hass.states.get("climate.hallway")
    assert state.state == HVACMode.HEAT


async def test_climate_on_off(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate on/off service."""

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].hvac_mode = "heat"
    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].device_on = True

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("climate.hallway")
    assert state.state == HVACMode.HEAT

    mock_client.async_set_ac_state_property.return_value = {
        "result": {"status": "Success"}
    }

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: state.entity_id},
        blocking=True,
    )

    state = hass.states.get("climate.hallway")
    assert state.state == HVACMode.OFF

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: state.entity_id},
        blocking=True,
    )

    state = hass.states.get("climate.hallway")
    assert state.state == HVACMode.HEAT


async def test_climate_service_failed(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate service failed."""

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].hvac_mode = "heat"
    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].device_on = True

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("climate.hallway")
    assert state.state == HVACMode.HEAT

    mock_client.async_set_ac_state_property.return_value = {
        "result": {"status": "Error", "failureReason": "Did not work"}
    }

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: state.entity_id},
            blocking=True,
        )

    state = hass.states.get("climate.hallway")
    assert state.state == HVACMode.HEAT


async def test_climate_assumed_state(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate assumed state service."""

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].hvac_mode = "heat"
    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].device_on = True

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("climate.hallway")
    assert state.state == HVACMode.HEAT

    mock_client.async_set_ac_state_property.return_value = {
        "result": {"status": "Success"}
    }

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ASSUME_STATE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_STATE: "off"},
        blocking=True,
    )

    state = hass.states.get("climate.hallway")
    assert state.state == HVACMode.OFF


async def test_climate_no_fan_no_swing(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate fan."""

    state = hass.states.get("climate.hallway")
    assert state.attributes["fan_mode"] == "high"
    assert state.attributes["swing_mode"] == "stopped"

    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].fan_mode = None
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].swing_mode = None
    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].fan_modes = None
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].swing_modes = None

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("climate.hallway")
    assert state.attributes["fan_mode"] is None
    assert state.attributes["swing_mode"] is None
    assert state.attributes["fan_modes"] is None
    assert state.attributes["swing_modes"] is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_climate_set_timer(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate Set Timer service."""

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("climate.hallway")
    assert hass.states.get("sensor.hallway_timer_end_time").state == STATE_UNKNOWN

    mock_client.async_set_timer.return_value = {"status": "failure"}

    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_TIMER,
            {
                ATTR_ENTITY_ID: state.entity_id,
            },
            blocking=True,
        )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_TIMER,
            {
                ATTR_ENTITY_ID: state.entity_id,
                ATTR_MINUTES: 30,
            },
            blocking=True,
        )

    mock_client.async_set_timer.return_value = {
        "status": "success",
        "result": {"id": "SzTGE4oZ4D"},
    }

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ENABLE_TIMER,
        {
            ATTR_ENTITY_ID: state.entity_id,
            ATTR_MINUTES: 30,
        },
        blocking=True,
    )

    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].timer_on = True
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].timer_id = "SzTGE4oZ4D"
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].timer_state_on = False
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].timer_time = datetime(2022, 6, 6, 12, 00, 00, tzinfo=dt_util.UTC)

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.hallway_timer_end_time").state
        == "2022-06-06T12:00:00+00:00"
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_climate_pure_boost(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate pure boost service."""

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("climate.kitchen")
    state2 = hass.states.get("switch.kitchen_pure_boost")
    assert state2.state == STATE_OFF

    with pytest.raises(
        MultipleInvalid,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_PURE_BOOST,
            {
                ATTR_ENTITY_ID: state.entity_id,
                ATTR_INDOOR_INTEGRATION: True,
                ATTR_OUTDOOR_INTEGRATION: True,
                ATTR_SENSITIVITY: "sensitive",
            },
            blocking=True,
        )

    mock_client.async_set_pureboost.return_value = {
        "status": "success",
        "result": {
            "enabled": True,
            "sensitivity": "S",
            "measurements_integration": True,
            "ac_integration": False,
            "geo_integration": False,
            "prime_integration": True,
        },
    }

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ENABLE_PURE_BOOST,
        {
            ATTR_ENTITY_ID: state.entity_id,
            ATTR_AC_INTEGRATION: False,
            ATTR_GEO_INTEGRATION: False,
            ATTR_INDOOR_INTEGRATION: True,
            ATTR_OUTDOOR_INTEGRATION: True,
            ATTR_SENSITIVITY: "sensitive",
        },
        blocking=True,
    )

    mock_client.async_get_devices_data.return_value.parsed[
        "AAZZAAZZ"
    ].pure_boost_enabled = True
    mock_client.async_get_devices_data.return_value.parsed[
        "AAZZAAZZ"
    ].pure_sensitivity = "s"
    mock_client.async_get_devices_data.return_value.parsed[
        "AAZZAAZZ"
    ].pure_measure_integration = True
    mock_client.async_get_devices_data.return_value.parsed[
        "AAZZAAZZ"
    ].pure_prime_integration = True

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("switch.kitchen_pure_boost").state == STATE_ON
    assert (
        hass.states.get(
            "binary_sensor.kitchen_pure_boost_linked_with_indoor_air_quality"
        ).state
        == STATE_ON
    )
    assert (
        hass.states.get(
            "binary_sensor.kitchen_pure_boost_linked_with_outdoor_air_quality"
        ).state
        == STATE_ON
    )
    assert hass.states.get("sensor.kitchen_pure_sensitivity").state == "s"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_climate_climate_react(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate react custom service."""

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state_climate = hass.states.get("climate.hallway")

    with pytest.raises(
        MultipleInvalid,
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

    mock_client.async_set_climate_react.return_value = {
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
    }

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

    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].smart_on = True
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].smart_type = "temperature"
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].smart_low_temp_threshold = 5.5
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].smart_high_temp_threshold = 30.5
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].smart_low_state = {
        "on": True,
        "targetTemperature": 25,
        "temperatureUnit": "C",
        "mode": "heat",
        "fanLevel": "low",
        "swing": "stopped",
        "horizontalSwing": "stopped",
        "light": "on",
    }
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].smart_high_state = {
        "on": True,
        "targetTemperature": 15,
        "temperatureUnit": "C",
        "mode": "cool",
        "fanLevel": "high",
        "swing": "stopped",
        "horizontalSwing": "stopped",
        "light": "on",
    }

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("switch.hallway_climate_react").state == STATE_ON
    assert (
        hass.states.get("sensor.hallway_climate_react_low_temperature_threshold").state
        == "5.5"
    )
    assert (
        hass.states.get("sensor.hallway_climate_react_high_temperature_threshold").state
        == "30.5"
    )
    assert hass.states.get("sensor.hallway_climate_react_type").state == "temperature"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_climate_climate_react_fahrenheit(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate react custom service with fahrenheit."""

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("climate.hallway")

    mock_client.async_set_climate_react.return_value = {
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
    }

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ENABLE_CLIMATE_REACT,
        {
            ATTR_ENTITY_ID: state.entity_id,
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

    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].smart_on = True
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].smart_type = "temperature"
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].smart_low_temp_threshold = 0
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].smart_high_temp_threshold = 25
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].smart_low_state = {
        "on": True,
        "targetTemperature": 85,
        "temperatureUnit": "F",
        "mode": "heat",
        "fanLevel": "low",
        "swing": "stopped",
        "horizontalSwing": "stopped",
        "light": "on",
    }
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].smart_high_state = {
        "on": True,
        "targetTemperature": 65,
        "temperatureUnit": "F",
        "mode": "cool",
        "fanLevel": "high",
        "swing": "stopped",
        "horizontalSwing": "stopped",
        "light": "on",
    }

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("switch.hallway_climate_react").state == STATE_ON
    assert (
        hass.states.get("sensor.hallway_climate_react_low_temperature_threshold").state
        == "0"
    )
    assert (
        hass.states.get("sensor.hallway_climate_react_high_temperature_threshold").state
        == "25"
    )
    assert hass.states.get("sensor.hallway_climate_react_type").state == "temperature"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_climate_full_ac_state(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate Full AC state service."""

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("climate.hallway")
    assert state.state == HVACMode.HEAT

    with pytest.raises(
        MultipleInvalid,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_FULL_STATE,
            {
                ATTR_ENTITY_ID: state.entity_id,
                ATTR_TARGET_TEMPERATURE: 22,
            },
            blocking=True,
        )

    mock_client.async_set_ac_states.return_value = {"result": {"status": "Success"}}

    await hass.services.async_call(
        DOMAIN,
        SERVICE_FULL_STATE,
        {
            ATTR_ENTITY_ID: state.entity_id,
            ATTR_MODE: "cool",
            ATTR_TARGET_TEMPERATURE: 22,
            ATTR_FAN_MODE: "high",
            ATTR_SWING_MODE: "stopped",
            ATTR_HORIZONTAL_SWING_MODE: "stopped",
            ATTR_LIGHT: "on",
        },
        blocking=True,
    )

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].hvac_mode = "cool"
    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].device_on = True
    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].target_temp = 22
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].fan_mode = "high"
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].swing_mode = "stopped"
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].horizontal_swing_mode = "stopped"
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].light_mode = "on"

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("climate.hallway")

    assert state.state == HVACMode.COOL
    assert state.attributes["temperature"] == 22


async def test_climate_fan_mode_and_swing_mode_not_supported(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo climate fan_mode and swing_mode not supported is raising error."""

    state = hass.states.get("climate.hallway")
    assert state.attributes["fan_mode"] == "high"
    assert state.attributes["swing_mode"] == "stopped"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_SWING_MODE: "faulty_swing_mode"},
            blocking=True,
        )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_FAN_MODE: "faulty_fan_mode"},
            blocking=True,
        )

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("climate.hallway")
    assert state.attributes["fan_mode"] == "high"
    assert state.attributes["swing_mode"] == "stopped"


async def test_climate_get_device_capabilities(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Sensibo climate Get device capabilitites service."""

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_DEVICE_CAPABILITIES,
        {ATTR_ENTITY_ID: "climate.hallway", ATTR_HVAC_MODE: "heat"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot

    with pytest.raises(
        ServiceValidationError, match="The entity does not support the chosen mode"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_DEVICE_CAPABILITIES,
            {ATTR_ENTITY_ID: "climate.hallway", ATTR_HVAC_MODE: "heat_cool"},
            blocking=True,
            return_response=True,
        )
