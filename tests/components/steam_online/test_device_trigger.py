"""The tests for Steam device triggers."""

import pytest
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


@pytest.mark.skip
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

    entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        ACCOUNT_1,
        device_id=device_entry.id,
        config_entry=config_entry,
    )
    entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        ACCOUNT_2,
        device_id=device_entry.id,
        config_entry=config_entry,
    )

    expected_triggers = [
        # TODO
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


async def test_if_fires_on_state_change(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test for turn_on and turn_off triggers firing."""
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

    hass.states.async_set(primary_sensor.entity_id, STATE_AWAY)
    hass.states.async_set(test_sensor.entity_id, STATE_AWAY)

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
                        "type": TRIGGER_FRIEND_GAME_CHANGED,
                    },
                    "action": {
                        "service": "test.automation",
                    },
                },
            ]
        },
    )

    # Primary user changes state should not trigger action
    hass.states.async_set(primary_sensor.entity_id, STATE_ONLINE)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Friend changes state should not trigger action
    hass.states.async_set(test_sensor.entity_id, STATE_ONLINE)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Primary user changes game should not trigger action
    hass.states.async_set(
        primary_sensor.entity_id, STATE_ONLINE, attributes={"game_id": "123"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Friend changes game should trigger action
    hass.states.async_set(
        test_sensor.entity_id, STATE_ONLINE, attributes={"game_id": "123"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
