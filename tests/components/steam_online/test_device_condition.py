"""The tests for Steam device conditions."""

from __future__ import annotations

from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.sensor import DOMAIN as SENSOR_PLATFORM
from homeassistant.components.steam_online.const import (
    CONDITION_PRIMARY_GAME,
    CONF_ACCOUNT,
    DOMAIN,
    STATE_ONLINE,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_get_device_automations

PRIMARY_USER_ID = "123456789"


async def test_get_conditions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected conditions from a steam_online."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, f"steam_{PRIMARY_USER_ID}")},
    )
    entity_registry.async_get_or_create(
        SENSOR_PLATFORM, DOMAIN, "5678", device_id=device_entry.id
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
    config_entry = MockConfigEntry(domain="test", data={CONF_ACCOUNT: PRIMARY_USER_ID})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    primary_sensor = entity_registry.async_get_or_create(
        DOMAIN, "test", PRIMARY_USER_ID, device_id=device_entry.id
    )
    test_sensor = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    # Creating and setting the states and attributes for the primary and secondary
    hass.states.async_set(
        primary_sensor.entity_id, STATE_ONLINE, attributes={"game_id": "123"}
    )

    hass.states.async_set(test_sensor.entity_id, STATE_ONLINE, attributes={})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    # "trigger": {"platform": "event", "event_type": "test_event1"},
                    "trigger": {
                        "platform": "state",
                        "entity_id": primary_sensor.entity_id,
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
                                "- {{ trigger.event.event_type }}"
                            )
                        },
                    },
                },
            ]
        },
    )
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(
        test_sensor.entity_id, STATE_ONLINE, attributes={"game_id": "123"}
    )
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    # assert service_calls[0].data["some"] == "is_same - event - test_event1"

    # hass.states.async_set("steam_online.entity", STATE_OFF)
    # hass.bus.async_fire("test_event1")
    # hass.bus.async_fire("test_event2")
    # await hass.async_block_till_done()
    # assert len(service_calls) == 2
    # assert service_calls[1].data["some"] == "is_off - event - test_event2"
