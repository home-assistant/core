"""The tests for Humidifier device triggers."""
import datetime

import pytest
from pytest_unordered import unordered
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
    async_fire_time_changed,
    async_get_device_automations,
    async_mock_service,
)


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


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
    entity_entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )
    hass.states.async_set(
        entity_entry.entity_id,
        STATE_ON,
        {
            const.ATTR_HUMIDITY: 23,
            const.ATTR_CURRENT_HUMIDITY: 48,
            ATTR_MODE: "home",
            const.ATTR_AVAILABLE_MODES: ["home", "away"],
            ATTR_SUPPORTED_FEATURES: 1,
        },
    )
    humidifier_trigger_types = ["current_humidity_changed", "target_humidity_changed"]
    toggle_trigger_types = ["turned_on", "turned_off", "changed_states"]
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        }
        for trigger in humidifier_trigger_types
    ]
    expected_triggers += [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        }
        for trigger in toggle_trigger_types
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


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
    entity_entry = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        "5678",
        device_id=device_entry.id,
        entity_category=entity_category,
        hidden_by=hidden_by,
    )
    humidifier_trigger_types = ["target_humidity_changed"]
    toggle_trigger_types = ["turned_on", "turned_off", "changed_states"]
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": True},
        }
        for trigger in humidifier_trigger_types
    ]
    expected_triggers += [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": True},
        }
        for trigger in toggle_trigger_types
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


async def test_if_fires_on_state_change(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    calls,
) -> None:
    """Test for turn_on and turn_off triggers firing."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    hass.states.async_set(
        entry.entity_id,
        STATE_ON,
        {
            const.ATTR_HUMIDITY: 23,
            const.ATTR_CURRENT_HUMIDITY: 35,
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
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
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
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
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
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
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
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
                        "type": "current_humidity_changed",
                        "below": 30,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "current_humidity_changed_below"},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
                        "type": "current_humidity_changed",
                        "above": 40,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "current_humidity_changed_above"},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
                        "type": "current_humidity_changed",
                        "above": 40,
                        "for": {"seconds": 5},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "current_humidity_changed_above_for"},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
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
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
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
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
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

    # Fake that the humidity target is changing
    hass.states.async_set(
        entry.entity_id,
        STATE_ON,
        {const.ATTR_HUMIDITY: 7, const.ATTR_CURRENT_HUMIDITY: 35},
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "target_humidity_changed_below"

    # Fake that the current humidity is changing
    hass.states.async_set(
        entry.entity_id,
        STATE_ON,
        {const.ATTR_HUMIDITY: 7, const.ATTR_CURRENT_HUMIDITY: 18},
    )
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "current_humidity_changed_below"

    # Fake that the humidity target is changing
    hass.states.async_set(
        entry.entity_id,
        STATE_ON,
        {const.ATTR_HUMIDITY: 37, const.ATTR_CURRENT_HUMIDITY: 18},
    )
    await hass.async_block_till_done()
    assert len(calls) == 3
    assert calls[2].data["some"] == "target_humidity_changed_above"

    # Fake that the current humidity is changing
    hass.states.async_set(
        entry.entity_id,
        STATE_ON,
        {const.ATTR_HUMIDITY: 37, const.ATTR_CURRENT_HUMIDITY: 41},
    )
    await hass.async_block_till_done()
    assert len(calls) == 4
    assert calls[3].data["some"] == "current_humidity_changed_above"

    # Wait 6 minutes
    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(minutes=6))
    await hass.async_block_till_done()
    assert len(calls) == 6
    assert {calls[4].data["some"], calls[5].data["some"]} == {
        "current_humidity_changed_above_for",
        "target_humidity_changed_above_for",
    }

    # Fake turn off
    hass.states.async_set(
        entry.entity_id,
        STATE_OFF,
        {const.ATTR_HUMIDITY: 37, const.ATTR_CURRENT_HUMIDITY: 41},
    )
    await hass.async_block_till_done()
    assert len(calls) == 8
    assert {calls[6].data["some"], calls[7].data["some"]} == {
        "turn_off device - humidifier.test_5678 - on - off - None",
        "turn_on_or_off device - humidifier.test_5678 - on - off - None",
    }

    # Fake turn on
    hass.states.async_set(
        entry.entity_id,
        STATE_ON,
        {const.ATTR_HUMIDITY: 37, const.ATTR_CURRENT_HUMIDITY: 41},
    )
    await hass.async_block_till_done()
    assert len(calls) == 10
    assert {calls[8].data["some"], calls[9].data["some"]} == {
        "turn_on device - humidifier.test_5678 - off - on - None",
        "turn_on_or_off device - humidifier.test_5678 - off - on - None",
    }


async def test_if_fires_on_state_change_legacy(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    calls,
) -> None:
    """Test for turn_on and turn_off triggers firing."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    hass.states.async_set(
        entry.entity_id,
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
                        "device_id": device_entry.id,
                        "entity_id": entry.entity_id,
                        "type": "target_humidity_changed",
                        "below": 20,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "target_humidity_changed_below"},
                    },
                },
            ]
        },
    )

    # Fake that the humidity is changing
    hass.states.async_set(entry.entity_id, STATE_ON, {const.ATTR_HUMIDITY: 7})
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "target_humidity_changed_below"


async def test_invalid_config(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, calls
) -> None:
    """Test for turn_on and turn_off triggers firing."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

    hass.states.async_set(
        entry.entity_id,
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
                        "entity_id": entry.id,
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
    hass.states.async_set(entry.entity_id, STATE_ON, {const.ATTR_HUMIDITY: 7})
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
            "entity_id": "01234568901234568901234568901",
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
            "entity_id": "01234568901234568901234568901",
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
            "entity_id": "01234568901234568901234568901",
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
