"""The tests for Humidifier device triggers."""
import voluptuous_serialize
import pytest

from homeassistant.components.humidifier import DOMAIN, const, device_trigger
from homeassistant.setup import async_setup_component
import homeassistant.components.automation as automation
from homeassistant.helpers import device_registry, config_validation as cv

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_mock_service,
    mock_device_registry,
    mock_registry,
    async_get_device_automations,
)


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
    """Track calls to a mock serivce."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(hass, device_reg, entity_reg):
    """Test we get the expected triggers from a humidifier device."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(DOMAIN, "test", "5678", device_id=device_entry.id)
    entity_id = f"{DOMAIN}.test_5678"
    hass.states.async_set(
        entity_id,
        const.OPERATION_MODE_DRY,
        {
            const.ATTR_HUMIDIFIER_ACTION: const.CURRENT_HUMIDIFIER_IDLE,
            const.ATTR_CURRENT_HUMIDITY: 23,
            const.ATTR_CURRENT_TEMPERATURE: 18,
            const.ATTR_WATER_LEVEL: 40,
        },
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "operation_mode_changed",
            "device_id": device_entry.id,
            "entity_id": entity_id,
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "current_temperature_changed",
            "device_id": device_entry.id,
            "entity_id": entity_id,
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "current_humidity_changed",
            "device_id": device_entry.id,
            "entity_id": entity_id,
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "water_level_changed",
            "device_id": device_entry.id,
            "entity_id": entity_id,
        },
    ]
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, expected_triggers)


async def test_if_fires_on_state_change(hass, calls):
    """Test for turn_on and turn_off triggers firing."""
    hass.states.async_set(
        "humidifier.entity",
        const.OPERATION_MODE_DRY,
        {
            const.ATTR_HUMIDIFIER_ACTION: const.CURRENT_HUMIDIFIER_IDLE,
            const.ATTR_CURRENT_HUMIDITY: 23,
            const.ATTR_CURRENT_TEMPERATURE: 18,
            const.ATTR_WATER_LEVEL: 40,
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
                        "type": "operation_mode_changed",
                        "to": const.OPERATION_MODE_AUTO,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "operation_mode_changed"},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "humidifier.entity",
                        "type": "current_temperature_changed",
                        "above": 20,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "current_temperature_changed"},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "humidifier.entity",
                        "type": "current_humidity_changed",
                        "below": 10,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "current_humidity_changed"},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "humidifier.entity",
                        "type": "water_level_changed",
                        "below": 30,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "water_level_changed"},
                    },
                },
            ]
        },
    )

    # Fake that the operation mode is changing
    hass.states.async_set(
        "humidifier.entity",
        const.OPERATION_MODE_AUTO,
        {
            const.ATTR_HUMIDIFIER_ACTION: const.CURRENT_HUMIDIFIER_DRY,
            const.ATTR_CURRENT_HUMIDITY: 23,
            const.ATTR_CURRENT_TEMPERATURE: 18,
            const.ATTR_WATER_LEVEL: 40,
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "operation_mode_changed"

    # Fake that the temperature is changing
    hass.states.async_set(
        "humidifier.entity",
        const.OPERATION_MODE_AUTO,
        {
            const.ATTR_HUMIDIFIER_ACTION: const.CURRENT_HUMIDIFIER_DRY,
            const.ATTR_CURRENT_HUMIDITY: 23,
            const.ATTR_CURRENT_TEMPERATURE: 23,
            const.ATTR_WATER_LEVEL: 40,
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "current_temperature_changed"

    # Fake that the humidity is changing
    hass.states.async_set(
        "humidifier.entity",
        const.OPERATION_MODE_AUTO,
        {
            const.ATTR_HUMIDIFIER_ACTION: const.CURRENT_HUMIDIFIER_DRY,
            const.ATTR_CURRENT_HUMIDITY: 7,
            const.ATTR_CURRENT_TEMPERATURE: 23,
            const.ATTR_WATER_LEVEL: 40,
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 3
    assert calls[2].data["some"] == "current_humidity_changed"

    # Fake that the water level is changing
    hass.states.async_set(
        "humidifier.entity",
        const.OPERATION_MODE_AUTO,
        {
            const.ATTR_HUMIDIFIER_ACTION: const.CURRENT_HUMIDIFIER_DRY,
            const.ATTR_CURRENT_HUMIDITY: 7,
            const.ATTR_CURRENT_TEMPERATURE: 23,
            const.ATTR_WATER_LEVEL: 20,
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 4
    assert calls[3].data["some"] == "water_level_changed"


async def test_get_trigger_capabilities_operation_mode(hass):
    """Test we get the expected capabilities from a humidifier trigger."""
    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            "platform": "device",
            "domain": "humidifier",
            "type": "operation_mode_changed",
            "entity_id": "humidifier.upstairs",
            "to": "heat",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [{"name": "for", "optional": True, "type": "positive_time_period_dict"}]


@pytest.mark.parametrize(
    "type",
    ["current_temperature_changed", "current_humidity_changed", "water_level_changed"],
)
async def test_get_trigger_capabilities_temp_humid(hass, type):
    """Test we get the expected capabilities from a humidifier trigger."""
    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            "platform": "device",
            "domain": "humidifier",
            "type": "current_temperature_changed",
            "entity_id": "humidifier.upstairs",
            "above": "23",
        },
    )

    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "description": {"suffix": "°C"},
            "name": "above",
            "optional": True,
            "type": "float",
        },
        {
            "description": {"suffix": "°C"},
            "name": "below",
            "optional": True,
            "type": "float",
        },
        {"name": "for", "optional": True, "type": "positive_time_period_dict"},
    ]
