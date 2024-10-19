from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.steam_online.const import (
    DOMAIN,
    STATE_AWAY,
    STATE_ONLINE,
    TRIGGER_FRIEND_GAME_CHANGED,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import ACCOUNT_1, ACCOUNT_2, create_entry

from tests.common import async_get_device_automations


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected triggers from a steam_online."""
    config_entry = create_entry(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, ACCOUNT_1)},
    )

    expected_triggers = [
        {
            "domain": DOMAIN,
            "platform": "device",
            "type": TRIGGER_FRIEND_GAME_CHANGED,
            "device_id": device_entry.id,
            "metadata": {},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


async def test_triggers_on_game_change(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test that the correct triggers fire when the game being played changes."""
    config_entry = create_entry(hass)

    # Set up the device
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, ACCOUNT_1)},
    )

    # Set up the primary sensor
    primary_sensor = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        ACCOUNT_1,
        device_id=device_entry.id,
        config_entry=config_entry,
    )

    # Set up the test sensor
    test_sensor = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        ACCOUNT_2,
        device_id=device_entry.id,
        config_entry=config_entry,
    )

    hass.states.async_set(primary_sensor.entity_id, STATE_AWAY)
    hass.states.async_set(test_sensor.entity_id, STATE_AWAY)
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )

    # Set up automation to listen to game_id changes for the test sensor
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": triggers,
                    "condition": [],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "game_changed - {{ trigger.platform }} - {{ trigger.entity_id }} - {{ trigger.to_state.attributes.game_id }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Change game on test_sensor to trigger the automation
    hass.states.async_set(
        test_sensor.entity_id, STATE_ONLINE, attributes={"game_id": "123"}
    )
    await hass.async_block_till_done()

    # Assert the trigger has fired with the correct game_id
    assert len(service_calls) == 1
    assert (
        service_calls[0].data["some"]
        == f"game_changed - state - {test_sensor.entity_id} - 123"
    )

    # Change game again on test_sensor to a new game, should trigger again
    hass.states.async_set(
        test_sensor.entity_id, STATE_ONLINE, attributes={"game_id": "456"}
    )
    await hass.async_block_till_done()

    # Assert the second trigger fired with the new game_id
    assert len(service_calls) == 2
    assert (
        service_calls[1].data["some"]
        == f"game_changed - state - {test_sensor.entity_id} - 456"
    )

    # Change game back on test_sensor to the first game, should trigger
    hass.states.async_set(
        test_sensor.entity_id, STATE_ONLINE, attributes={"game_id": "123"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 3
    assert (
        service_calls[2].data["some"]
        == f"game_changed - state - {test_sensor.entity_id} - 123"
    )

    # Change game on primary_sensor, shouldn't trigger
    hass.states.async_set(
        primary_sensor.entity_id, STATE_ONLINE, attributes={"game_id": "789"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 3

    # Change game to None, should trigger
    hass.states.async_set(
        test_sensor.entity_id, STATE_ONLINE, attributes={"game_id": None}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 4
    assert (
        service_calls[3].data["some"]
        == f"game_changed - state - {test_sensor.entity_id} - None"
    )
