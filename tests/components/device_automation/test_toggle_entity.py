"""The test for device automation toggle entity helpers."""

from datetime import timedelta

from probatio import Invalid
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components import automation
from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util


async def test_if_fires_on_state_change(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test for turn_on and turn_off triggers firing.

    This is a sanity test for the toggle entity device automation helper, this is
    tested by each integration too.
    """
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        "switch", "test", "5678", device_id=device_entry.id
    )

    hass.states.async_set(entry.entity_id, STATE_ON)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": "switch",
                        "device_id": device_entry.id,
                        "entity_id": entry.entity_id,
                        "type": "turned_on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "turn_on {{ trigger.platform }}"
                                " - {{ trigger.entity_id }}"
                                " - {{ trigger.from_state.state }}"
                                " - {{ trigger.to_state.state }}"
                                " - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": "switch",
                        "device_id": device_entry.id,
                        "entity_id": entry.entity_id,
                        "type": "turned_off",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "turn_off {{ trigger.platform }}"
                                " - {{ trigger.entity_id }}"
                                " - {{ trigger.from_state.state }}"
                                " - {{ trigger.to_state.state }}"
                                " - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": "switch",
                        "device_id": device_entry.id,
                        "entity_id": entry.entity_id,
                        "type": "changed_states",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "turn_on_or_off {{ trigger.platform }}"
                                " - {{ trigger.entity_id }}"
                                " - {{ trigger.from_state.state }}"
                                " - {{ trigger.to_state.state }}"
                                " - {{ trigger.for }}"
                            )
                        },
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(entry.entity_id).state == STATE_ON
    assert len(service_calls) == 0

    hass.states.async_set(entry.entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(service_calls) == 2
    assert {service_calls[0].data["some"], service_calls[1].data["some"]} == {
        f"turn_off device - {entry.entity_id} - on - off - None",
        f"turn_on_or_off device - {entry.entity_id} - on - off - None",
    }

    hass.states.async_set(entry.entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert len(service_calls) == 4
    assert {service_calls[2].data["some"], service_calls[3].data["some"]} == {
        f"turn_on device - {entry.entity_id} - off - on - None",
        f"turn_on_or_off device - {entry.entity_id} - off - on - None",
    }


@pytest.mark.parametrize("trigger", ["turned_off", "changed_states"])
async def test_if_fires_on_state_change_with_for(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
    trigger: str,
) -> None:
    """Test for triggers firing with delay."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        "switch", "test", "5678", device_id=device_entry.id
    )

    hass.states.async_set(entry.entity_id, STATE_ON)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": "switch",
                        "device_id": device_entry.id,
                        "entity_id": entry.entity_id,
                        "type": trigger,
                        "for": {"seconds": 5},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "turn_off {{ trigger.platform }}"
                                " - {{ trigger.entity_id }}"
                                " - {{ trigger.from_state.state }}"
                                " - {{ trigger.to_state.state }}"
                                " - {{ trigger.for }}"
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(entry.entity_id).state == STATE_ON
    assert len(service_calls) == 0

    hass.states.async_set(entry.entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(service_calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    await hass.async_block_till_done()
    assert (
        service_calls[0].data["some"]
        == f"turn_off device - {entry.entity_id} - on - off - 0:00:05"
    )


def test_turned_on_with_bad_for_is_invalid() -> None:
    """Test the trigger type selects the schema that reports the error."""
    with pytest.raises(Invalid, match="expected dict at 'for'"):
        toggle_entity.TRIGGER_SCHEMA(
            {
                "platform": "device",
                "domain": "light",
                "device_id": "abcdefgh",
                "entity_id": "light.test",
                "type": "turned_on",
                "for": "later",
            }
        )


@pytest.mark.parametrize("trigger", ["turned_on", "turned_off", "changed_states"])
@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        pytest.param(STATE_UNAVAILABLE, STATE_OFF, id="unavailable_to_off"),
        pytest.param(STATE_UNAVAILABLE, STATE_ON, id="unavailable_to_on"),
        pytest.param(STATE_UNKNOWN, STATE_OFF, id="unknown_to_off"),
        pytest.param(STATE_UNKNOWN, STATE_ON, id="unknown_to_on"),
        pytest.param(STATE_OFF, STATE_UNAVAILABLE, id="off_to_unavailable"),
        pytest.param(STATE_ON, STATE_UNAVAILABLE, id="on_to_unavailable"),
    ],
)
async def test_does_not_fire_on_availability_change(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
    trigger: str,
    from_state: str,
    to_state: str,
) -> None:
    """Test triggers don't fire when an entity becomes available or unavailable."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        "switch", "test", "5678", device_id=device_entry.id
    )

    hass.states.async_set(entry.entity_id, from_state)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": "switch",
                        "device_id": device_entry.id,
                        "entity_id": entry.entity_id,
                        "type": trigger,
                    },
                    "action": {"service": "test.automation"},
                }
            ]
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set(entry.entity_id, to_state)
    await hass.async_block_till_done()
    assert len(service_calls) == 0
