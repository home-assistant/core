"""Tests for the HomematicIP Cloud fan."""

from copy import deepcopy
import json

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from .helper import (
    FIXTURE_DATA,
    HomeFactory,
    async_manipulate_test_data,
    get_and_check_entity_basics,
)


async def test_ventilation_fan(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicIP ventilation actuator."""
    entity_id = "fan.universalaktor_ventilation"
    entity_name = "Universalaktor Ventilation"
    device_model = "HmIP-WUA"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Universalaktor"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_PERCENTAGE] == 1

    channel = hmip_device.functionalChannels[1]

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert channel.mock_calls[-1][0] == "async_set_ventilation_state"
    assert channel.mock_calls[-1][1] == ("NO_VENTILATION",)

    await async_manipulate_test_data(
        hass, hmip_device, "ventilationState", "NO_VENTILATION", channel=1
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert channel.mock_calls[-1][0] == "async_set_ventilation_state"
    assert channel.mock_calls[-1][1] == ("VENTILATION",)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 50},
        blocking=True,
    )
    assert channel.mock_calls[-1][0] == "async_set_ventilation_level"
    assert channel.mock_calls[-1][1] == (0.5,)

    await async_manipulate_test_data(
        hass, hmip_device, "ventilationLevel", 0.5, channel=1
    )
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE] == 50


async def test_ventilation_fan_percentage_zero_stops_ventilation(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that a percentage of zero stops ventilating instead of setting level 0."""
    entity_id = "fan.universalaktor_ventilation"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Universalaktor"]
    )
    hmip_device = mock_hap.hmip_device_by_entity_id.get(entity_id)
    channel = hmip_device.functionalChannels[1]

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 0},
        blocking=True,
    )

    assert channel.mock_calls[-1][0] == "async_set_ventilation_state"
    assert channel.mock_calls[-1][1] == ("NO_VENTILATION",)


async def test_ventilation_fan_turn_on_with_percentage(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that turning on with a percentage sets the level in one call."""
    entity_id = "fan.universalaktor_ventilation"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Universalaktor"]
    )
    hmip_device = mock_hap.hmip_device_by_entity_id.get(entity_id)
    channel = hmip_device.functionalChannels[1]

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 40},
        blocking=True,
    )

    assert channel.mock_calls[-1][0] == "async_set_ventilation_level"
    assert channel.mock_calls[-1][1] == (0.4,)


async def test_no_fan_for_other_channel_role(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that a universal actuator that does not ventilate gets no fan."""
    device = deepcopy(json.loads(FIXTURE_DATA)["devices"]["3014F7110000000000000WUA"])
    device["id"] = "3014F7110000000000000DIM"
    device["label"] = "Dimmaktor"
    device["functionalChannels"]["1"]["channelRole"] = "DIMMER"

    await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Universalaktor", "Dimmaktor"], extra_devices=[device]
    )

    assert hass.states.get("fan.universalaktor_ventilation") is not None
    assert hass.states.get("fan.dimmaktor_ventilation") is None
