"""The tests for the geolocation trigger."""
import pytest

from homeassistant.components import automation, zone
from homeassistant.core import Context
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service, mock_component
from tests.components.automation import common


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
        "geo_location.entity",
        "hello",
        {"latitude": 32.881011, "longitude": -117.234758, "source": "test_source"},
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "geo_location",
                    "source": "test_source",
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
                            )
                        )
                    },
                },
            }
        },
    )

    hass.states.async_set(
        "geo_location.entity",
        "hello",
        {"latitude": 32.880586, "longitude": -117.237564},
        context=context,
    )
    await hass.async_block_till_done()

    assert 1 == len(calls)
    assert calls[0].context.parent_id == context.id
    assert (
        "geo_location - geo_location.entity - hello - hello - test"
        == calls[0].data["some"]
    )

    # Set out of zone again so we can trigger call
    hass.states.async_set(
        "geo_location.entity",
        "hello",
        {"latitude": 32.881011, "longitude": -117.234758},
    )
    await hass.async_block_till_done()

    await common.async_turn_off(hass)
    await hass.async_block_till_done()

    hass.states.async_set(
        "geo_location.entity",
        "hello",
        {"latitude": 32.880586, "longitude": -117.237564},
    )
    await hass.async_block_till_done()

    assert 1 == len(calls)


async def test_if_not_fires_for_enter_on_zone_leave(hass, calls):
    """Test for not firing on zone leave."""
    hass.states.async_set(
        "geo_location.entity",
        "hello",
        {"latitude": 32.880586, "longitude": -117.237564, "source": "test_source"},
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "geo_location",
                    "source": "test_source",
                    "zone": "zone.test",
                    "event": "enter",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(
        "geo_location.entity",
        "hello",
        {"latitude": 32.881011, "longitude": -117.234758},
    )
    await hass.async_block_till_done()

    assert 0 == len(calls)


async def test_if_fires_on_zone_leave(hass, calls):
    """Test for firing on zone leave."""
    hass.states.async_set(
        "geo_location.entity",
        "hello",
        {"latitude": 32.880586, "longitude": -117.237564, "source": "test_source"},
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "geo_location",
                    "source": "test_source",
                    "zone": "zone.test",
                    "event": "leave",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(
        "geo_location.entity",
        "hello",
        {"latitude": 32.881011, "longitude": -117.234758, "source": "test_source"},
    )
    await hass.async_block_till_done()

    assert 1 == len(calls)


async def test_if_not_fires_for_leave_on_zone_enter(hass, calls):
    """Test for not firing on zone enter."""
    hass.states.async_set(
        "geo_location.entity",
        "hello",
        {"latitude": 32.881011, "longitude": -117.234758, "source": "test_source"},
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "geo_location",
                    "source": "test_source",
                    "zone": "zone.test",
                    "event": "leave",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(
        "geo_location.entity",
        "hello",
        {"latitude": 32.880586, "longitude": -117.237564},
    )
    await hass.async_block_till_done()

    assert 0 == len(calls)


async def test_if_fires_on_zone_appear(hass, calls):
    """Test for firing if entity appears in zone."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "geo_location",
                    "source": "test_source",
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
                            )
                        )
                    },
                },
            }
        },
    )

    # Entity appears in zone without previously existing outside the zone.
    context = Context()
    hass.states.async_set(
        "geo_location.entity",
        "hello",
        {"latitude": 32.880586, "longitude": -117.237564, "source": "test_source"},
        context=context,
    )
    await hass.async_block_till_done()

    assert 1 == len(calls)
    assert calls[0].context.parent_id == context.id
    assert (
        "geo_location - geo_location.entity -  - hello - test" == calls[0].data["some"]
    )


async def test_if_fires_on_zone_disappear(hass, calls):
    """Test for firing if entity disappears from zone."""
    hass.states.async_set(
        "geo_location.entity",
        "hello",
        {"latitude": 32.880586, "longitude": -117.237564, "source": "test_source"},
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "geo_location",
                    "source": "test_source",
                    "zone": "zone.test",
                    "event": "leave",
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
                            )
                        )
                    },
                },
            }
        },
    )

    # Entity disappears from zone without new coordinates outside the zone.
    hass.states.async_remove("geo_location.entity")
    await hass.async_block_till_done()

    assert 1 == len(calls)
    assert (
        "geo_location - geo_location.entity - hello -  - test" == calls[0].data["some"]
    )
