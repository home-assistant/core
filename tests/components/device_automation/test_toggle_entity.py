"""The test for device automation toggle entity helpers."""
from datetime import timedelta

import pytest

import homeassistant.components.automation as automation
from homeassistant.const import CONF_PLATFORM, STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, async_mock_service
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_if_fires_on_state_change(hass, calls, enable_custom_integrations):
    """Test for turn_on and turn_off triggers firing.

    This is a sanity test for the toggle entity device automation helper, this is
    tested by each integration too.
    """
    platform = getattr(hass.components, "test.switch")

    platform.init()
    assert await async_setup_component(
        hass, "switch", {"switch": {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1, ent2, ent3 = platform.ENTITIES

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": "switch",
                        "device_id": "",
                        "entity_id": ent1.entity_id,
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
                        "domain": "switch",
                        "device_id": "",
                        "entity_id": ent1.entity_id,
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
                        "domain": "switch",
                        "device_id": "",
                        "entity_id": ent1.entity_id,
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
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_ON
    assert len(calls) == 0

    hass.states.async_set(ent1.entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert {calls[0].data["some"], calls[1].data["some"]} == {
        f"turn_off device - {ent1.entity_id} - on - off - None",
        f"turn_on_or_off device - {ent1.entity_id} - on - off - None",
    }

    hass.states.async_set(ent1.entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert len(calls) == 4
    assert {calls[2].data["some"], calls[3].data["some"]} == {
        f"turn_on device - {ent1.entity_id} - off - on - None",
        f"turn_on_or_off device - {ent1.entity_id} - off - on - None",
    }


@pytest.mark.parametrize("trigger", ["turned_off", "changed_states"])
async def test_if_fires_on_state_change_with_for(
    hass, calls, enable_custom_integrations, trigger
):
    """Test for triggers firing with delay."""
    platform = getattr(hass.components, "test.switch")

    platform.init()
    assert await async_setup_component(
        hass, "switch", {"switch": {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1, ent2, ent3 = platform.ENTITIES

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": "switch",
                        "device_id": "",
                        "entity_id": ent1.entity_id,
                        "type": trigger,
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
    assert hass.states.get(ent1.entity_id).state == STATE_ON
    assert len(calls) == 0

    hass.states.async_set(ent1.entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    await hass.async_block_till_done()
    assert calls[0].data["some"] == "turn_off device - {} - on - off - 0:00:05".format(
        ent1.entity_id
    )
