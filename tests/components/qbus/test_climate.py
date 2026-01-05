"""Test Qbus light entities."""

from datetime import timedelta
from unittest.mock import MagicMock, call

import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntity,
    HVACAction,
    HVACMode,
)
from homeassistant.components.qbus.climate import STATE_REQUEST_DELAY
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.util import dt as dt_util

from tests.common import async_fire_mqtt_message, async_fire_time_changed
from tests.typing import MqttMockHAClient

_CURRENT_TEMPERATURE = 21.5
_SET_TEMPERATURE = 20.5
_REGIME = "COMFORT"

_PAYLOAD_CLIMATE_STATE_TEMP = (
    f'{{"id":"UL20","properties":{{"setTemp":{_SET_TEMPERATURE}}},"type":"event"}}'
)
_PAYLOAD_CLIMATE_STATE_TEMP_FULL = f'{{"id":"UL20","properties":{{"currRegime":"MANUEEL","currTemp":{_CURRENT_TEMPERATURE},"setTemp":{_SET_TEMPERATURE}}},"type":"state"}}'

_PAYLOAD_CLIMATE_STATE_PRESET = (
    f'{{"id":"UL20","properties":{{"currRegime":"{_REGIME}"}},"type":"event"}}'
)
_PAYLOAD_CLIMATE_STATE_PRESET_FULL = f'{{"id":"UL20","properties":{{"currRegime":"{_REGIME}","currTemp":{_CURRENT_TEMPERATURE},"setTemp":22.0}},"type":"state"}}'

_PAYLOAD_CLIMATE_SET_TEMP = f'{{"id": "UL20", "type": "state", "properties": {{"setTemp": {_SET_TEMPERATURE}}}}}'
_PAYLOAD_CLIMATE_SET_PRESET = (
    '{"id": "UL20", "type": "state", "properties": {"currRegime": "COMFORT"}}'
)

_TOPIC_CLIMATE_STATE = "cloudapp/QBUSMQTTGW/UL1/UL20/state"
_TOPIC_CLIMATE_SET_STATE = "cloudapp/QBUSMQTTGW/UL1/UL20/setState"
_TOPIC_GET_STATE = "cloudapp/QBUSMQTTGW/getState"

_CLIMATE_ENTITY_ID = "climate.living_th"


async def test_climate(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    setup_integration: None,
) -> None:
    """Test climate temperature & preset."""

    # Set temperature
    mqtt_mock.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID,
            ATTR_TEMPERATURE: _SET_TEMPERATURE,
        },
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        _TOPIC_CLIMATE_SET_STATE, _PAYLOAD_CLIMATE_SET_TEMP, 0, False
    )

    # Simulate a partial state response
    async_fire_mqtt_message(hass, _TOPIC_CLIMATE_STATE, _PAYLOAD_CLIMATE_STATE_TEMP)
    await hass.async_block_till_done()

    # Check state
    entity = hass.states.get(_CLIMATE_ENTITY_ID)
    assert entity
    assert entity.attributes[ATTR_TEMPERATURE] == _SET_TEMPERATURE
    assert entity.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert entity.attributes[ATTR_PRESET_MODE] == "MANUEEL"
    assert entity.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert entity.state == HVACMode.HEAT

    # After a delay, a full state request should've been sent
    _wait_and_assert_state_request(hass, mqtt_mock)

    # Simulate a full state response
    async_fire_mqtt_message(
        hass, _TOPIC_CLIMATE_STATE, _PAYLOAD_CLIMATE_STATE_TEMP_FULL
    )
    await hass.async_block_till_done()

    # Check state after full state response
    entity = hass.states.get(_CLIMATE_ENTITY_ID)
    assert entity
    assert entity.attributes[ATTR_TEMPERATURE] == _SET_TEMPERATURE
    assert entity.attributes[ATTR_CURRENT_TEMPERATURE] == _CURRENT_TEMPERATURE
    assert entity.attributes[ATTR_PRESET_MODE] == "MANUEEL"
    assert entity.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert entity.state == HVACMode.HEAT

    # Set preset
    mqtt_mock.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID,
            ATTR_PRESET_MODE: _REGIME,
        },
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        _TOPIC_CLIMATE_SET_STATE, _PAYLOAD_CLIMATE_SET_PRESET, 0, False
    )

    # Simulate a partial state response
    async_fire_mqtt_message(hass, _TOPIC_CLIMATE_STATE, _PAYLOAD_CLIMATE_STATE_PRESET)
    await hass.async_block_till_done()

    # Check state
    entity = hass.states.get(_CLIMATE_ENTITY_ID)
    assert entity
    assert entity.attributes[ATTR_TEMPERATURE] == _SET_TEMPERATURE
    assert entity.attributes[ATTR_CURRENT_TEMPERATURE] == _CURRENT_TEMPERATURE
    assert entity.attributes[ATTR_PRESET_MODE] == _REGIME
    assert entity.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert entity.state == HVACMode.HEAT

    # After a delay, a full state request should've been sent
    _wait_and_assert_state_request(hass, mqtt_mock)

    # Simulate a full state response
    async_fire_mqtt_message(
        hass, _TOPIC_CLIMATE_STATE, _PAYLOAD_CLIMATE_STATE_PRESET_FULL
    )
    await hass.async_block_till_done()

    # Check state after full state response
    entity = hass.states.get(_CLIMATE_ENTITY_ID)
    assert entity
    assert entity.attributes[ATTR_TEMPERATURE] == 22.0
    assert entity.attributes[ATTR_CURRENT_TEMPERATURE] == _CURRENT_TEMPERATURE
    assert entity.attributes[ATTR_PRESET_MODE] == _REGIME
    assert entity.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert entity.state == HVACMode.HEAT


async def test_climate_when_invalid_state_received(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    setup_integration: None,
) -> None:
    """Test climate when no valid state is received."""

    platform: EntityPlatform = hass.data["entity_components"][CLIMATE_DOMAIN]
    entity: ClimateEntity = next(
        (
            entity
            for entity in platform.entities
            if entity.entity_id == _CLIMATE_ENTITY_ID
        ),
        None,
    )

    assert entity
    entity.async_schedule_update_ha_state = MagicMock()

    # Simulate state response
    async_fire_mqtt_message(hass, _TOPIC_CLIMATE_STATE, "")
    await hass.async_block_till_done()

    entity.async_schedule_update_ha_state.assert_not_called()


async def test_climate_with_fast_subsequent_changes(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    setup_integration: None,
) -> None:
    """Test climate with fast subsequent changes."""

    # Simulate two subsequent partial state responses
    async_fire_mqtt_message(hass, _TOPIC_CLIMATE_STATE, _PAYLOAD_CLIMATE_STATE_TEMP)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, _TOPIC_CLIMATE_STATE, _PAYLOAD_CLIMATE_STATE_TEMP)
    await hass.async_block_till_done()

    # State request should be requested only once
    _wait_and_assert_state_request(hass, mqtt_mock)


async def test_climate_with_unknown_preset(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    setup_integration: None,
) -> None:
    """Test climate with passing an unknown preset value."""

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID,
                ATTR_PRESET_MODE: "What is cooler than being cool?",
            },
            blocking=True,
        )


def _wait_and_assert_state_request(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    mqtt_mock.reset_mock()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(STATE_REQUEST_DELAY))
    mqtt_mock.async_publish.assert_has_calls(
        [call(_TOPIC_GET_STATE, '["UL20"]', 0, False)],
        any_order=True,
    )
