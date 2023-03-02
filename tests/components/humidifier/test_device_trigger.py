"""The tests for Humidifier device triggers."""
import datetime

import pytest
import voluptuous_serialize

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.humidifier import DOMAIN, const, device_trigger
from homeassistant.const import (
    ATTR_MODE,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.entity_registry import RegistryEntryHider
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_fire_time_changed,
    async_get_device_automations,
    async_mock_service,
)
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected triggers from a humidifier device."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )
    entity_id = f"{DOMAIN}.test_5678"
    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            const.ATTR_HUMIDITY: 23,
            ATTR_MODE: "home",
            const.ATTR_AVAILABLE_MODES: ["home", "away"],
            ATTR_SUPPORTED_FEATURES: 1,
        },
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": entity_id,
            "metadata": {"secondary": False},
        }
        for trigger in [
            "target_humidity_changed",
            "turned_off",
            "turned_on",
            "changed_states",
        ]
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert_lists_same(triggers, expected_triggers)


@pytest.mark.parametrize(
    ("hidden_by", "entity_category"),
    (
        (RegistryEntryHider.INTEGRATION, None),
        (RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ),
)
async def test_get_triggers_hidden_auxiliary(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hidden_by,
    entity_category,
) -> None:
    """Test we get the expected triggers from a hidden or auxiliary entity."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        "5678",
        device_id=device_entry.id,
        entity_category=entity_category,
        hidden_by=hidden_by,
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
            "metadata": {"secondary": True},
        }
        for trigger in [
            "target_humidity_changed",
            "turned_off",
            "turned_on",
            "changed_states",
        ]
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert_lists_same(triggers, expected_triggers)


async def test_if_fires_on_state_change(hass: HomeAssistant, calls) -> None:
    """Test for turn_on and turn_off triggers firing."""
    hass.states.async_set(
        "humidifier.entity",
        STATE_ON,
        {
            const.ATTR_HUMIDITY: 23,
            ATTR_MODE: "home",
            const.ATTR_AVAILABLE_MODES: ["home", "away"],
            ATTR_SUPPORTED_FEATURES: 1,
        },
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
                        "device_id": "",
                        "entity_id": "humidifier.entity",
                        "type": "target_humidity_changed",
                        "below": 20,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "target_humidity_changed_below"},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "humidifier.entity",
                        "type": "target_humidity_changed",
                        "above": 30,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "target_humidity_changed_above"},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "humidifier.entity",
                        "type": "target_humidity_changed",
                        "above": 30,
                        "for": {"seconds": 5},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "target_humidity_changed_above_for"},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "humidifier.entity",
                        "type": "turned_on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "turn_on {{ trigger.%s }}"
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
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "humidifier.entity",
                        "type": "turned_off",
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
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "humidifier.entity",
                        "type": "changed_states",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "turn_on_or_off {{ trigger.%s }}"
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
                },
            ]
        },
    )

    # Fake that the humidity is changing
    hass.states.async_set("humidifier.entity", STATE_ON, {const.ATTR_HUMIDITY: 7})
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "target_humidity_changed_below"

    # Fake that the humidity is changing
    hass.states.async_set("humidifier.entity", STATE_ON, {const.ATTR_HUMIDITY: 37})
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "target_humidity_changed_above"

    # Wait 6 minutes
    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(minutes=6))
    await hass.async_block_till_done()
    assert len(calls) == 3
    assert calls[2].data["some"] == "target_humidity_changed_above_for"

    # Fake turn off
    hass.states.async_set("humidifier.entity", STATE_OFF, {const.ATTR_HUMIDITY: 37})
    await hass.async_block_till_done()
    assert len(calls) == 5
    assert {calls[3].data["some"], calls[4].data["some"]} == {
        "turn_off device - humidifier.entity - on - off - None",
        "turn_on_or_off device - humidifier.entity - on - off - None",
    }

    # Fake turn on
    hass.states.async_set("humidifier.entity", STATE_ON, {const.ATTR_HUMIDITY: 37})
    await hass.async_block_till_done()
    assert len(calls) == 7
    assert {calls[5].data["some"], calls[6].data["some"]} == {
        "turn_on device - humidifier.entity - off - on - None",
        "turn_on_or_off device - humidifier.entity - off - on - None",
    }


async def test_invalid_config(hass: HomeAssistant, calls) -> None:
    """Test for turn_on and turn_off triggers firing."""
    hass.states.async_set(
        "humidifier.entity",
        STATE_ON,
        {
            const.ATTR_HUMIDITY: 23,
            ATTR_MODE: "home",
            const.ATTR_AVAILABLE_MODES: ["home", "away"],
            ATTR_SUPPORTED_FEATURES: 1,
        },
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
                        "device_id": "",
                        "entity_id": "humidifier.entity",
                        "type": "target_humidity_changed",
                        "below": 20,
                        "invalid": "invalid",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "target_humidity_changed"},
                    },
                },
            ]
        },
    )

    # Fake that the humidity is changing
    hass.states.async_set("humidifier.entity", STATE_ON, {const.ATTR_HUMIDITY: 7})
    await hass.async_block_till_done()
    # Should not trigger for invalid config
    assert len(calls) == 0


async def test_get_trigger_capabilities_on(hass: HomeAssistant) -> None:
    """Test we get the expected capabilities from a humidifier trigger."""
    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            "platform": "device",
            "domain": "humidifier",
            "type": "turned_on",
            "entity_id": "humidifier.upstairs",
            "above": "23",
        },
    )

    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [{"name": "for", "optional": True, "type": "positive_time_period_dict"}]


async def test_get_trigger_capabilities_off(hass: HomeAssistant) -> None:
    """Test we get the expected capabilities from a humidifier trigger."""
    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            "platform": "device",
            "domain": "humidifier",
            "type": "turned_off",
            "entity_id": "humidifier.upstairs",
            "above": "23",
        },
    )

    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [{"name": "for", "optional": True, "type": "positive_time_period_dict"}]


async def test_get_trigger_capabilities_humidity(hass: HomeAssistant) -> None:
    """Test we get the expected capabilities from a humidifier trigger."""
    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            "platform": "device",
            "domain": "humidifier",
            "type": "target_humidity_changed",
            "entity_id": "humidifier.upstairs",
            "above": "23",
        },
    )

    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "description": {"suffix": "%"},
            "name": "above",
            "optional": True,
            "type": "integer",
        },
        {
            "description": {"suffix": "%"},
            "name": "below",
            "optional": True,
            "type": "integer",
        },
        {"name": "for", "optional": True, "type": "positive_time_period_dict"},
    ]
