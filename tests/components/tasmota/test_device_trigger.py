"""The tests for Tasmota device triggers."""

import copy
import json
from unittest.mock import Mock, patch

from hatasmota.switch import TasmotaSwitchTriggerConfig
import pytest
from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.tasmota import _LOGGER
from homeassistant.components.tasmota.const import DEFAULT_PREFIX, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import async_initialize_triggers
from homeassistant.setup import async_setup_component

from .test_common import DEFAULT_CONFIG, remove_device

from tests.common import async_fire_mqtt_message, async_get_device_automations
from tests.typing import MqttMockHAClient, WebSocketGenerator


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


async def test_get_triggers_btn(
    hass: HomeAssistant,
    device_reg,
    entity_reg,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test we get the expected triggers from a discovered mqtt device."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["btn"][0] = 1
    config["btn"][1] = 1
    config["so"]["13"] = 1
    config["so"]["73"] = 1
    mac = config["mac"]

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "discovery_id": "00000049A3BC_button_1_SINGLE",
            "type": "button_short_press",
            "subtype": "button_1",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "discovery_id": "00000049A3BC_button_2_SINGLE",
            "type": "button_short_press",
            "subtype": "button_2",
            "metadata": {},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


async def test_get_triggers_swc(
    hass: HomeAssistant,
    device_reg,
    entity_reg,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test we get the expected triggers from a discovered mqtt device."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 0
    mac = config["mac"]

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "discovery_id": "00000049A3BC_switch_1_TOGGLE",
            "type": "button_short_press",
            "subtype": "switch_1",
            "metadata": {},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


async def test_get_unknown_triggers(
    hass: HomeAssistant,
    device_reg,
    entity_reg,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test we don't get unknown triggers."""
    # Discover a device without device triggers
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = -1
    mac = config["mac"]

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "00000049A3BC_switch_0_2",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == []


async def test_get_non_existing_triggers(
    hass: HomeAssistant,
    device_reg,
    entity_reg,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test getting non existing triggers."""
    # Discover a device without device triggers
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config1["swc"][0] = -1
    mac = config1["mac"]

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config1))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == []


@pytest.mark.no_fail_on_log_exception
async def test_discover_bad_triggers(
    hass: HomeAssistant,
    device_reg,
    entity_reg,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test exception handling when discovering trigger."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 0
    mac = config["mac"]

    # Trigger an exception when the entity is discovered
    with patch(
        "hatasmota.discovery.get_switch_triggers",
        return_value=[object()],
    ):
        async_fire_mqtt_message(
            hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config)
        )
        await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == []

    # Trigger an exception when the entity is discovered
    class FakeTrigger(TasmotaSwitchTriggerConfig):
        """Bad TasmotaSwitchTriggerConfig to cause exceptions."""

        @property
        def is_active(self):
            return True

    with patch(
        "hatasmota.discovery.get_switch_triggers",
        return_value=[
            FakeTrigger(
                event=None,
                idx=1,
                mac=None,
                source=None,
                subtype=None,
                switchname=None,
                trigger_topic=None,
                type=None,
            )
        ],
    ):
        async_fire_mqtt_message(
            hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config)
        )
        await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == []

    # Rediscover without exception
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()

    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "discovery_id": "00000049A3BC_switch_1_TOGGLE",
            "type": "button_short_press",
            "subtype": "switch_1",
            "metadata": {},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


async def test_update_remove_triggers(
    hass: HomeAssistant,
    device_reg,
    entity_reg,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test triggers can be updated and removed."""
    # Discover a device with toggle + hold trigger
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config1["swc"][0] = 5
    mac = config1["mac"]

    # Discover a device with toggle + double press trigger
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config2["swc"][0] = 8

    # Discover a device with no trigger
    config3 = copy.deepcopy(DEFAULT_CONFIG)
    config3["swc"][0] = -1

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config1))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    expected_triggers1 = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "discovery_id": "00000049A3BC_switch_1_TOGGLE",
            "type": "button_short_press",
            "subtype": "switch_1",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "discovery_id": "00000049A3BC_switch_1_HOLD",
            "type": "button_long_press",
            "subtype": "switch_1",
            "metadata": {},
        },
    ]
    expected_triggers2 = copy.deepcopy(expected_triggers1)
    expected_triggers2[1]["type"] = "button_double_press"

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    for expected in expected_triggers1:
        assert expected in triggers

    # Update trigger
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config2))
    await hass.async_block_till_done()

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    for expected in expected_triggers2:
        assert expected in triggers

    # Remove trigger
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config3))
    await hass.async_block_till_done()

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == []


async def test_if_fires_on_mqtt_message_btn(
    hass: HomeAssistant, device_reg, calls, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test button triggers firing."""
    # Discover a device with 2 device triggers
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["btn"][0] = 1
    config["btn"][2] = 1
    config["so"]["73"] = 1
    mac = config["mac"]

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "00000049A3BC_button_1_SINGLE",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press_1")},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "00000049A3BC_button_3_SINGLE",
                        "subtype": "button_3",
                        "type": "button_short_press",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press_3")},
                    },
                },
            ]
        },
    )

    # Fake button 1 single press.
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Button1":{"Action":"SINGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "short_press_1"

    # Fake button 3 single press.
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Button3":{"Action":"SINGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "short_press_3"


async def test_if_fires_on_mqtt_message_swc(
    hass: HomeAssistant, device_reg, calls, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test switch triggers firing."""
    # Discover a device with 2 device triggers
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 0
    config["swc"][1] = 0
    config["swc"][2] = 9
    config["swn"][2] = "custom_switch"
    mac = config["mac"]

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "00000049A3BC_switch_1_TOGGLE",
                        "type": "button_short_press",
                        "subtype": "switch_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press_1")},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "00000049A3BC_switch_2_TOGGLE",
                        "type": "button_short_press",
                        "subtype": "switch_2",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press_2")},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "00000049A3BC_switch_3_HOLD",
                        "subtype": "switch_3",
                        "type": "button_double_press",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("long_press_3")},
                    },
                },
            ]
        },
    )

    # Fake switch 1 short press.
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "short_press_1"

    # Fake switch 2 short press.
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch2":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "short_press_2"

    # Fake switch 3 long press.
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"custom_switch":{"Action":"HOLD"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 3
    assert calls[2].data["some"] == "long_press_3"


async def test_if_fires_on_mqtt_message_late_discover(
    hass: HomeAssistant, device_reg, calls, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test triggers firing of MQTT device triggers discovered after setup."""
    # Discover a device without device triggers
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config1["swc"][0] = -1
    mac = config1["mac"]

    # Discover a device with 2 device triggers
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config2["swc"][0] = 0
    config2["swc"][3] = 9
    config2["swn"][3] = "custom_switch"

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config1))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "00000049A3BC_switch_1_TOGGLE",
                        "type": "button_short_press",
                        "subtype": "switch_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "00000049A3BC_switch_4_HOLD",
                        "type": "switch_4",
                        "subtype": "button_double_press",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("double_press")},
                    },
                },
            ]
        },
    )

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config2))
    await hass.async_block_till_done()

    # Fake short press.
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "short_press"

    # Fake long press.
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"custom_switch":{"Action":"HOLD"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "double_press"


async def test_if_fires_on_mqtt_message_after_update(
    hass: HomeAssistant, device_reg, calls, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test triggers firing after update."""
    # Discover a device with device trigger
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config1["swc"][0] = 0
    config2["swc"][0] = 0
    config2["tp"][1] = "status"
    mac = config1["mac"]

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config1))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "00000049A3BC_switch_1_TOGGLE",
                        "type": "button_short_press",
                        "subtype": "switch_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )

    # Fake short press.
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Update the trigger with different topic
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config2))
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 1

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/status/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 2

    # Update the trigger with same topic
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config2))
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 2

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/status/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 3


async def test_no_resubscribe_same_topic(
    hass: HomeAssistant, device_reg, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test subscription to topics without change."""
    # Discover a device with device trigger
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 0
    mac = config["mac"]

    mqtt_mock.async_subscribe.reset_mock()

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "00000049A3BC_switch_1_TOGGLE",
                        "type": "button_short_press",
                        "subtype": "switch_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )

    call_count = mqtt_mock.async_subscribe.call_count
    assert call_count == 1
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()
    assert mqtt_mock.async_subscribe.call_count == call_count


async def test_not_fires_on_mqtt_message_after_remove_by_mqtt(
    hass: HomeAssistant, device_reg, calls, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test triggers not firing after removal."""
    # Discover a device with device trigger
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 0
    mac = config["mac"]

    mqtt_mock.async_subscribe.reset_mock()

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "00000049A3BC_switch_1_TOGGLE",
                        "type": "button_short_press",
                        "subtype": "switch_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )

    # Fake short press.
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Remove the trigger
    config["swc"][0] = -1
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Rediscover the trigger
    config["swc"][0] = 0
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_not_fires_on_mqtt_message_after_remove_from_registry(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_reg,
    calls,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test triggers not firing after removal."""
    assert await async_setup_component(hass, "config", {})
    # Discover a device with device trigger
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 0
    mac = config["mac"]

    mqtt_mock.async_subscribe.reset_mock()

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "00000049A3BC_switch_1_TOGGLE",
                        "type": "button_short_press",
                        "subtype": "switch_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )

    # Fake short press.
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Remove the device
    await remove_device(hass, await hass_ws_client(hass), device_entry.id)
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_attach_remove(
    hass: HomeAssistant, device_reg, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test attach and removal of trigger."""
    # Discover a device with device trigger
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 0
    mac = config["mac"]

    mqtt_mock.async_subscribe.reset_mock()

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    calls = []

    def callback(trigger, context):
        calls.append(trigger["trigger"]["description"])

    remove = await async_initialize_triggers(
        hass,
        [
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": device_entry.id,
                "discovery_id": "00000049A3BC_switch_1_TOGGLE",
                "type": "button_short_press",
                "subtype": "switch_1",
            },
        ],
        callback,
        DOMAIN,
        "mock-name",
        _LOGGER.log,
    )

    # Fake short press.
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0] == "event 'tasmota_event'"

    # Remove the trigger
    remove()
    await hass.async_block_till_done()

    # Verify the triggers are no longer active
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_attach_remove_late(
    hass: HomeAssistant, device_reg, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test attach and removal of trigger."""
    # Discover a device without device triggers
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config1["swc"][0] = -1
    mac = config1["mac"]

    # Discover a device with device triggers
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config2["swc"][0] = 0

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config1))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    calls = []

    def callback(trigger, context):
        calls.append(trigger["trigger"]["description"])

    remove = await async_initialize_triggers(
        hass,
        [
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": device_entry.id,
                "discovery_id": "00000049A3BC_switch_1_TOGGLE",
                "type": "button_short_press",
                "subtype": "switch_1",
            },
        ],
        callback,
        DOMAIN,
        "mock-name",
        _LOGGER.log,
    )

    # Fake short press.
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 0

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config2))
    await hass.async_block_till_done()

    # Fake short press.
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0] == "event 'tasmota_event'"

    # Remove the trigger
    remove()
    await hass.async_block_till_done()

    # Verify the triggers are no longer active
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_attach_remove_late2(
    hass: HomeAssistant, device_reg, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test attach and removal of trigger."""
    # Discover a device without device triggers
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config1["swc"][0] = -1
    mac = config1["mac"]

    # Discover a device with device triggers
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config2["swc"][0] = 0

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config1))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    calls = []

    def callback(trigger, context):
        calls.append(trigger["trigger"]["description"])

    remove = await async_initialize_triggers(
        hass,
        [
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": device_entry.id,
                "discovery_id": "00000049A3BC_switch_1_TOGGLE",
                "type": "button_short_press",
                "subtype": "switch_1",
            },
        ],
        callback,
        DOMAIN,
        "mock-name",
        _LOGGER.log,
    )

    # Remove the trigger
    remove()
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config1))
    await hass.async_block_till_done()

    # Verify the triggers is not active
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_attach_remove_unknown1(
    hass: HomeAssistant, device_reg, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test attach and removal of unknown trigger."""
    # Discover a device without device triggers
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config1["swc"][0] = -1
    mac = config1["mac"]

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config1))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    remove = await async_initialize_triggers(
        hass,
        [
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": device_entry.id,
                "discovery_id": "00000049A3BC_switch_1_TOGGLE",
                "type": "button_short_press",
                "subtype": "switch_1",
            },
        ],
        Mock(),
        DOMAIN,
        "mock-name",
        _LOGGER.log,
    )

    # Remove the trigger
    remove()
    await hass.async_block_till_done()


async def test_attach_unknown_remove_device_from_registry(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_reg,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test attach and removal of device with unknown trigger."""
    assert await async_setup_component(hass, "config", {})
    # Discover a device without device triggers
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config1["swc"][0] = -1
    mac = config1["mac"]

    # Discover a device with device triggers
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config2["swc"][0] = 0

    # Discovery a device with device triggers to load Tasmota device trigger integration
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config2))
    await hass.async_block_till_done()

    # Forget the trigger
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config1))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    await async_initialize_triggers(
        hass,
        [
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": device_entry.id,
                "discovery_id": "00000049A3BC_switch_1_TOGGLE",
                "type": "button_short_press",
                "subtype": "switch_1",
            },
        ],
        Mock(),
        DOMAIN,
        "mock-name",
        _LOGGER.log,
    )

    # Remove the device
    await remove_device(hass, await hass_ws_client(hass), device_entry.id)
    await hass.async_block_till_done()


async def test_attach_remove_config_entry(
    hass: HomeAssistant, device_reg, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test trigger cleanup when removing a Tasmota config entry."""
    # Discover a device with device trigger
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["swc"][0] = 0
    mac = config["mac"]

    mqtt_mock.async_subscribe.reset_mock()

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    calls = []

    def callback(trigger, context):
        calls.append(trigger["trigger"]["description"])

    await async_initialize_triggers(
        hass,
        [
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": device_entry.id,
                "discovery_id": "00000049A3BC_switch_1_TOGGLE",
                "type": "button_short_press",
                "subtype": "switch_1",
            },
        ],
        callback,
        DOMAIN,
        "mock-name",
        _LOGGER.log,
    )

    # Fake short press.
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0] == "event 'tasmota_event'"

    # Remove the Tasmota config entry
    config_entries = hass.config_entries.async_entries("tasmota")
    await hass.config_entries.async_remove(config_entries[0].entry_id)
    await hass.async_block_till_done()

    # Verify the triggers are no longer active
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/stat/RESULT", '{"Switch1":{"Action":"TOGGLE"}}'
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
