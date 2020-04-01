"""The test for sensor device automation."""
from datetime import timedelta

import pytest

import homeassistant.components.automation as automation
from homeassistant.components.sensor import DOMAIN
from homeassistant.components.sensor.device_trigger import ENTITY_TRIGGERS
from homeassistant.const import CONF_PLATFORM, STATE_UNKNOWN, UNIT_PERCENTAGE
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_get_device_automation_capabilities,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)
from tests.testing_config.custom_components.test.sensor import DEVICE_CLASSES


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(hass, device_reg, entity_reg):
    """Test we get the expected triggers from a sensor."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    for device_class in DEVICE_CLASSES:
        entity_reg.async_get_or_create(
            DOMAIN,
            "test",
            platform.ENTITIES[device_class].unique_id,
            device_id=device_entry.id,
        )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger["type"],
            "device_id": device_entry.id,
            "entity_id": platform.ENTITIES[device_class].entity_id,
        }
        for device_class in DEVICE_CLASSES
        for trigger in ENTITY_TRIGGERS[device_class]
        if device_class != "none"
    ]
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert len(triggers) == 8
    assert triggers == expected_triggers


async def test_get_trigger_capabilities(hass, device_reg, entity_reg):
    """Test we get the expected capabilities from a sensor trigger."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN,
        "test",
        platform.ENTITIES["battery"].unique_id,
        device_id=device_entry.id,
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    expected_capabilities = {
        "extra_fields": [
            {
                "description": {"suffix": UNIT_PERCENTAGE},
                "name": "above",
                "optional": True,
                "type": "float",
            },
            {
                "description": {"suffix": UNIT_PERCENTAGE},
                "name": "below",
                "optional": True,
                "type": "float",
            },
            {"name": "for", "optional": True, "type": "positive_time_period_dict"},
        ]
    }
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert len(triggers) == 1
    for trigger in triggers:
        capabilities = await async_get_device_automation_capabilities(
            hass, "trigger", trigger
        )
        assert capabilities == expected_capabilities


async def test_get_trigger_capabilities_none(hass, device_reg, entity_reg):
    """Test we get the expected capabilities from a sensor trigger."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    triggers = [
        {
            "platform": "device",
            "device_id": "8770c43885354d5fa27604db6817f63f",
            "domain": "sensor",
            "entity_id": "sensor.beer",
            "type": "is_battery_level",
        },
        {
            "platform": "device",
            "device_id": "8770c43885354d5fa27604db6817f63f",
            "domain": "sensor",
            "entity_id": platform.ENTITIES["none"].entity_id,
            "type": "is_battery_level",
        },
    ]

    expected_capabilities = {}
    for trigger in triggers:
        capabilities = await async_get_device_automation_capabilities(
            hass, "trigger", trigger
        )
        assert capabilities == expected_capabilities


async def test_if_fires_not_on_above_below(hass, calls, caplog):
    """Test for value triggers firing."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    sensor1 = platform.ENTITIES["battery"]

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": sensor1.entity_id,
                        "type": "battery_level",
                    },
                    "action": {"service": "test.automation"},
                }
            ]
        },
    )
    assert "must contain at least one of below, above" in caplog.text


async def test_if_fires_on_state_above(hass, calls):
    """Test for value triggers firing."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    sensor1 = platform.ENTITIES["battery"]

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": sensor1.entity_id,
                        "type": "battery_level",
                        "above": 10,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "bat_low {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                (
                                    "platform",
                                    "entity_id",
                                    "from_state.state",
                                    "to_state.state",
                                    "for",
                                )
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(sensor1.entity_id).state == STATE_UNKNOWN
    assert len(calls) == 0

    hass.states.async_set(sensor1.entity_id, 9)
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set(sensor1.entity_id, 11)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "bat_low device - {} - 9 - 11 - None".format(
        sensor1.entity_id
    )


async def test_if_fires_on_state_below(hass, calls):
    """Test for value triggers firing."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    sensor1 = platform.ENTITIES["battery"]

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": sensor1.entity_id,
                        "type": "battery_level",
                        "below": 10,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "bat_low {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                (
                                    "platform",
                                    "entity_id",
                                    "from_state.state",
                                    "to_state.state",
                                    "for",
                                )
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(sensor1.entity_id).state == STATE_UNKNOWN
    assert len(calls) == 0

    hass.states.async_set(sensor1.entity_id, 11)
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set(sensor1.entity_id, 9)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "bat_low device - {} - 11 - 9 - None".format(
        sensor1.entity_id
    )


async def test_if_fires_on_state_between(hass, calls):
    """Test for value triggers firing."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    sensor1 = platform.ENTITIES["battery"]

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": sensor1.entity_id,
                        "type": "battery_level",
                        "above": 10,
                        "below": 20,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "bat_low {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                (
                                    "platform",
                                    "entity_id",
                                    "from_state.state",
                                    "to_state.state",
                                    "for",
                                )
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(sensor1.entity_id).state == STATE_UNKNOWN
    assert len(calls) == 0

    hass.states.async_set(sensor1.entity_id, 9)
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set(sensor1.entity_id, 11)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "bat_low device - {} - 9 - 11 - None".format(
        sensor1.entity_id
    )

    hass.states.async_set(sensor1.entity_id, 21)
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.states.async_set(sensor1.entity_id, 19)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "bat_low device - {} - 21 - 19 - None".format(
        sensor1.entity_id
    )


async def test_if_fires_on_state_change_with_for(hass, calls):
    """Test for triggers firing with delay."""
    platform = getattr(hass.components, f"test.{DOMAIN}")

    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    sensor1 = platform.ENTITIES["battery"]

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": sensor1.entity_id,
                        "type": "battery_level",
                        "above": 10,
                        "for": {"seconds": 5},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "turn_off {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                (
                                    "platform",
                                    "entity_id",
                                    "from_state.state",
                                    "to_state.state",
                                    "for",
                                )
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(sensor1.entity_id).state == STATE_UNKNOWN
    assert len(calls) == 0

    hass.states.async_set(sensor1.entity_id, 11)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    await hass.async_block_till_done()
    assert calls[0].data[
        "some"
    ] == "turn_off device - {} - unknown - 11 - 0:00:05".format(sensor1.entity_id)
