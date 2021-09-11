"""The tests for the location automation."""
import pytest

from homeassistant.components import automation, zone
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, SERVICE_TURN_OFF
from homeassistant.core import Context
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service, mock_component
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


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


async def test_if_fires_on_zone_enter(hass, calls):
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
                        "some": "{{ trigger.%s }}"
                        % "}} - {{ trigger.".join(
                            (
                                "platform",
                                "entity_id",
                                "from_state.state",
                                "to_state.state",
                                "zone.name",
                                "id",
                            )
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


async def test_if_not_fires_for_enter_on_zone_leave(hass, calls):
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


async def test_if_fires_on_zone_leave(hass, calls):
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


async def test_if_not_fires_for_leave_on_zone_enter(hass, calls):
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


async def test_zone_condition(hass, calls):
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
