"""The tests for Steam device conditions."""

from __future__ import annotations

from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.steam_online.const import (
    CONDITION_PRIMARY_GAME,
    DOMAIN,
    STATE_ONLINE,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import ACCOUNT_1, ACCOUNT_2, create_entry

from tests.common import async_get_device_automations


async def test_get_conditions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected conditions from a steam_online."""
    config_entry = create_entry(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, ACCOUNT_1)},
    )
    expected_conditions = [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": CONDITION_PRIMARY_GAME,
            "device_id": device_entry.id,
            "metadata": {},
        },
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert conditions == unordered(expected_conditions)


async def test_if_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test for turn_on and turn_off conditions."""
    config_entry = create_entry(hass)

    # Setting up the device
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, ACCOUNT_1)},
    )

    # Setting up the primary sensor
    primary_sensor = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        ACCOUNT_1,
        device_id=device_entry.id,
        config_entry=config_entry,
    )

    # Setting up the test sensor
    test_sensor = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        ACCOUNT_2,
        device_id=device_entry.id,
        config_entry=config_entry,
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "state",
                        "entity_id": test_sensor.entity_id,
                    },
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device_entry.id,
                            "type": CONDITION_PRIMARY_GAME,
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "is_same "
                                "- {{ trigger.platform }} "
                                "- {{ trigger.entity_id }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Changing primary should not pass condition
    hass.states.async_set(
        primary_sensor.entity_id, STATE_ONLINE, attributes={"game_id": "123"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Condition passes when test_sensor starts playing same game as primary
    hass.states.async_set(
        test_sensor.entity_id, STATE_ONLINE, attributes={"game_id": "123"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == f"is_same - state - {test_sensor.entity_id}"

    # Condition does not pass when test_sensor starts playing different game
    hass.states.async_set(
        test_sensor.entity_id, STATE_ONLINE, attributes={"game_id": "321"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    # Condition does not pass when primary starts playing same game as test_sensor
    hass.states.async_set(
        primary_sensor.entity_id, STATE_ONLINE, attributes={"game_id": "321"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    # Does not trigger when the game is None
    hass.states.async_set(
        primary_sensor.entity_id, STATE_ONLINE, attributes={"game_id": None}
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        test_sensor.entity_id, STATE_ONLINE, attributes={"game_id": None}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    # Condition passes when they start playing the same game again
    hass.states.async_set(
        primary_sensor.entity_id, STATE_ONLINE, attributes={"game_id": "456"}
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        test_sensor.entity_id, STATE_ONLINE, attributes={"game_id": "456"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 2
    assert service_calls[0].data["some"] == f"is_same - state - {test_sensor.entity_id}"
