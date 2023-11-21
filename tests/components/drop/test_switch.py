"""Test DROP switch entities."""

from homeassistant.components.drop.const import DOMAIN as DROP_DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import (
    TEST_DATA_FILTER,
    TEST_DATA_FILTER_TOPIC,
    TEST_DATA_HUB,
    TEST_DATA_HUB_TOPIC,
    TEST_DATA_PROTECTION_VALVE,
    TEST_DATA_PROTECTION_VALVE_TOPIC,
    TEST_DATA_SOFTENER,
    TEST_DATA_SOFTENER_TOPIC,
)

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def test_switches_hub(
    hass: HomeAssistant, config_entry_hub, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP switches for hubs."""
    config_entry_hub.add_to_hass(hass)
    assert await async_setup_component(hass, DROP_DOMAIN, {})
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB)
    await hass.async_block_till_done()

    waterSupplySwitchName = "switch.hub_drop_1_c0ffee_water_supply"
    waterSupplySwitch = hass.states.get(waterSupplySwitchName)
    assert waterSupplySwitch
    assert waterSupplySwitch.state == STATE_ON

    # Test switch turn off method.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: waterSupplySwitchName},
        blocking=True,
    )

    waterSupplySwitch = hass.states.get(waterSupplySwitchName)
    assert waterSupplySwitch
    assert waterSupplySwitch.state == STATE_OFF

    # Test switch turn on method.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: waterSupplySwitchName},
        blocking=True,
    )

    waterSupplySwitch = hass.states.get(waterSupplySwitchName)
    assert waterSupplySwitch
    assert waterSupplySwitch.state == STATE_ON

    bypassSwitchName = "switch.hub_drop_1_c0ffee_treatment_bypass"
    bypassSwitch = hass.states.get(bypassSwitchName)
    assert bypassSwitch
    assert bypassSwitch.state == STATE_OFF

    # Test switch turn on method.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: bypassSwitchName},
        blocking=True,
    )

    bypassSwitch = hass.states.get(bypassSwitchName)
    assert bypassSwitch
    assert bypassSwitch.state == STATE_ON

    # Test switch turn off method.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: bypassSwitchName},
        blocking=True,
    )

    bypassSwitch = hass.states.get(bypassSwitchName)
    assert bypassSwitch
    assert bypassSwitch.state == STATE_OFF


async def test_switches_protection_valve(
    hass: HomeAssistant, config_entry_protection_valve, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP switches for protection valves."""
    config_entry_protection_valve.add_to_hass(hass)
    assert await async_setup_component(hass, DROP_DOMAIN, {})
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass, TEST_DATA_PROTECTION_VALVE_TOPIC, TEST_DATA_PROTECTION_VALVE
    )
    await hass.async_block_till_done()

    waterSupplySwitchName = "switch.protection_valve_water_supply"
    waterSupplySwitch = hass.states.get(waterSupplySwitchName)
    assert waterSupplySwitch
    assert waterSupplySwitch.state == STATE_ON

    # Test switch turn off method.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: waterSupplySwitchName},
        blocking=True,
    )

    waterSupplySwitch = hass.states.get(waterSupplySwitchName)
    assert waterSupplySwitch
    assert waterSupplySwitch.state == STATE_OFF

    # Test switch turn on method.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: waterSupplySwitchName},
        blocking=True,
    )

    waterSupplySwitch = hass.states.get(waterSupplySwitchName)
    assert waterSupplySwitch
    assert waterSupplySwitch.state == STATE_ON


async def test_switches_softener(
    hass: HomeAssistant, config_entry_softener, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP switches for softeners."""
    config_entry_softener.add_to_hass(hass)
    assert await async_setup_component(hass, DROP_DOMAIN, {})
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, TEST_DATA_SOFTENER_TOPIC, TEST_DATA_SOFTENER)
    await hass.async_block_till_done()

    bypassSwitchName = "switch.softener_treatment_bypass"
    bypassSwitch = hass.states.get(bypassSwitchName)
    assert bypassSwitch
    assert bypassSwitch.state == STATE_OFF

    # Test switch turn on method.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: bypassSwitchName},
        blocking=True,
    )

    bypassSwitch = hass.states.get(bypassSwitchName)
    assert bypassSwitch
    assert bypassSwitch.state == STATE_ON

    # Test switch turn off method.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: bypassSwitchName},
        blocking=True,
    )

    bypassSwitch = hass.states.get(bypassSwitchName)
    assert bypassSwitch
    assert bypassSwitch.state == STATE_OFF


async def test_switches_filter(
    hass: HomeAssistant, config_entry_filter, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP switches for filters."""
    config_entry_filter.add_to_hass(hass)
    assert await async_setup_component(hass, DROP_DOMAIN, {})
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, TEST_DATA_FILTER_TOPIC, TEST_DATA_FILTER)
    await hass.async_block_till_done()

    bypassSwitchName = "switch.filter_treatment_bypass"
    bypassSwitch = hass.states.get(bypassSwitchName)
    assert bypassSwitch
    assert bypassSwitch.state == STATE_OFF

    # Test switch turn on method.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: bypassSwitchName},
        blocking=True,
    )

    bypassSwitch = hass.states.get(bypassSwitchName)
    assert bypassSwitch
    assert bypassSwitch.state == STATE_ON

    # Test switch turn off method.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: bypassSwitchName},
        blocking=True,
    )

    bypassSwitch = hass.states.get(bypassSwitchName)
    assert bypassSwitch
    assert bypassSwitch.state == STATE_OFF
