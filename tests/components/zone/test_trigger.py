"""The tests for the location automation."""

import pytest

from homeassistant.components import automation, zone
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, SERVICE_TURN_OFF
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service, mock_component


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, "group")
    hass.loop.run_until_complete(
        async_setup_component(
            hass,
            zone.DOMAIN,
            {
                "zone": {
                    "name": "test",
                    "latitude": 32.880837,
                    "longitude": -117.237561,
                    "radius": 250,
                }
            },
        )
    )


async def test_if_fires_on_zone_enter(hass: HomeAssistant, calls) -> None:
    """Test for firing on zone enter."""
    context = Context()
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "zone",
                    "entity_id": "test.entity",
                    "zone": "zone.test",
                    "event": "enter",
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": (
                            "{{ trigger.platform }}"
                            " - {{ trigger.entity_id }}"
                            " - {{ trigger.from_state.state }}"
                            " - {{ trigger.to_state.state }}"
                            " - {{ trigger.zone.name }}"
                            " - {{ trigger.id }}"
                        )
                    },
                },
            }
        },
    )

    hass.states.async_set(
        "test.entity",
        "hello",
        {"latitude": 32.880586, "longitude": -117.237564},
        context=context,
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].context.parent_id == context.id
    assert calls[0].data["some"] == "zone - test.entity - hello - hello - test - 0"

    # Set out of zone again so we can trigger call
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )

    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.880586, "longitude": -117.237564}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_if_fires_on_zone_enter_uuid(hass: HomeAssistant, calls) -> None:
    """Test for firing on zone enter when device is specified by entity registry id."""
    context = Context()

    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        "test", "hue", "1234", suggested_object_id="entity"
    )
    assert entry.entity_id == "test.entity"

    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "zone",
                    "entity_id": entry.id,
                    "zone": "zone.test",
                    "event": "enter",
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": (
                            "{{ trigger.platform }}"
                            " - {{ trigger.entity_id }}"
                            " - {{ trigger.from_state.state }}"
                            " - {{ trigger.to_state.state }}"
                            " - {{ trigger.zone.name }}"
                            " - {{ trigger.id }}"
                        )
                    },
                },
            }
        },
    )

    hass.states.async_set(
        "test.entity",
        "hello",
        {"latitude": 32.880586, "longitude": -117.237564},
        context=context,
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].context.parent_id == context.id
    assert calls[0].data["some"] == "zone - test.entity - hello - hello - test - 0"

    # Set out of zone again so we can trigger call
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )

    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.880586, "longitude": -117.237564}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_if_not_fires_for_enter_on_zone_leave(hass: HomeAssistant, calls) -> None:
    """Test for not firing on zone leave."""
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.880586, "longitude": -117.237564}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "zone",
                    "entity_id": "test.entity",
                    "zone": "zone.test",
                    "event": "enter",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_if_fires_on_zone_leave(hass: HomeAssistant, calls) -> None:
    """Test for firing on zone leave."""
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.880586, "longitude": -117.237564}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "zone",
                    "entity_id": "test.entity",
                    "zone": "zone.test",
                    "event": "leave",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_if_not_fires_for_leave_on_zone_enter(hass: HomeAssistant, calls) -> None:
    """Test for not firing on zone enter."""
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "zone",
                    "entity_id": "test.entity",
                    "zone": "zone.test",
                    "event": "leave",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.880586, "longitude": -117.237564}
    )
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_zone_condition(hass: HomeAssistant, calls) -> None:
    """Test for zone condition."""
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.880586, "longitude": -117.237564}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "zone",
                    "entity_id": "test.entity",
                    "zone": "zone.test",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_unknown_zone(
    hass: HomeAssistant, calls, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for firing on zone enter."""
    context = Context()
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "My Automation",
                "trigger": {
                    "platform": "zone",
                    "entity_id": "test.entity",
                    "zone": "zone.no_such_zone",
                    "event": "enter",
                },
                "action": {
                    "service": "test.automation",
                },
            }
        },
    )

    assert (
        "Automation 'My Automation' is referencing non-existing zone"
        " 'zone.no_such_zone' in a zone trigger" not in caplog.text
    )

    hass.states.async_set(
        "test.entity",
        "hello",
        {"latitude": 32.880586, "longitude": -117.237564},
        context=context,
    )
    await hass.async_block_till_done()

    assert (
        "Automation 'My Automation' is referencing non-existing zone"
        " 'zone.no_such_zone' in a zone trigger" in caplog.text
    )
