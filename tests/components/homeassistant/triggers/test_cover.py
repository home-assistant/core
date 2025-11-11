"""The tests for the Cover automation."""

import pytest

from homeassistant.components import automation
from homeassistant.components.cover import ATTR_CURRENT_POSITION
from homeassistant.const import CONF_ENTITY_ID, CONF_PLATFORM, CONF_TARGET
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.common import mock_component


@pytest.fixture(autouse=True)
def setup_comp(hass: HomeAssistant) -> None:
    """Initialize components."""
    mock_component(hass, "group")


async def test_opens_trigger_fires_on_opening(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that opens trigger fires when cover starts opening."""
    hass.states.async_set("cover.test", "closed")
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "cover.opens",
                    CONF_TARGET: {CONF_ENTITY_ID: "cover.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("cover.test", "opening", context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_opens_trigger_fires_on_open(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that opens trigger fires when cover becomes open."""
    hass.states.async_set("cover.test", "closed")
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "cover.opens",
                    CONF_TARGET: {CONF_ENTITY_ID: "cover.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("cover.test", "open", context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_opens_trigger_fully_opened_option(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that opens trigger with fully_opened only fires at position 100."""
    hass.states.async_set("cover.test", "closed", {ATTR_CURRENT_POSITION: 0})

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "cover.opens",
                    CONF_TARGET: {CONF_ENTITY_ID: "cover.test"},
                    "fully_opened": True,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # Should not trigger at position 50
    hass.states.async_set("cover.test", "opening", {ATTR_CURRENT_POSITION: 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Should trigger at position 100
    hass.states.async_set("cover.test", "open", {ATTR_CURRENT_POSITION: 100})
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_opens_trigger_device_class_filter(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that opens trigger filters by device class."""
    hass.states.async_set("cover.curtain", "closed", {"device_class": "curtain"})
    hass.states.async_set("cover.garage", "closed", {"device_class": "garage"})

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "cover.opens",
                    CONF_TARGET: {
                        CONF_ENTITY_ID: ["cover.curtain", "cover.garage"]
                    },
                    "device_class": ["curtain"],
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # Should trigger for curtain
    hass.states.async_set("cover.curtain", "opening", {"device_class": "curtain"})
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    # Should not trigger for garage
    hass.states.async_set("cover.garage", "opening", {"device_class": "garage"})
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_does_not_fire_on_unavailable(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that trigger does not fire when state becomes unavailable."""
    hass.states.async_set("cover.test", "closed")

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "cover.opens",
                    CONF_TARGET: {CONF_ENTITY_ID: "cover.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("cover.test", "unavailable")
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_trigger_data_available(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that trigger data is available in action."""
    hass.states.async_set("cover.test", "closed")

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "cover.opens",
                    CONF_TARGET: {CONF_ENTITY_ID: "cover.test"},
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "entity_id": "{{ trigger.entity_id }}",
                        "from_state": "{{ trigger.from_state.state }}",
                        "to_state": "{{ trigger.to_state.state }}",
                    },
                },
            }
        },
    )

    hass.states.async_set("cover.test", "opening")
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["entity_id"] == "cover.test"
    assert service_calls[0].data["from_state"] == "closed"
    assert service_calls[0].data["to_state"] == "opening"


async def test_fires_with_multiple_entities(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the firing with multiple entities."""
    hass.states.async_set("cover.test1", "closed")
    hass.states.async_set("cover.test2", "closed")

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "cover.opens",
                    CONF_TARGET: {CONF_ENTITY_ID: ["cover.test1", "cover.test2"]},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("cover.test1", "opening")
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    hass.states.async_set("cover.test2", "opening")
    await hass.async_block_till_done()
    assert len(service_calls) == 2


async def test_closes_trigger_fires_on_closing(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that closes trigger fires when cover starts closing."""
    hass.states.async_set("cover.test", "open")
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "cover.closes",
                    CONF_TARGET: {CONF_ENTITY_ID: "cover.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("cover.test", "closing", context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_closes_trigger_fires_on_closed(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that closes trigger fires when cover becomes closed."""
    hass.states.async_set("cover.test", "open")
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "cover.closes",
                    CONF_TARGET: {CONF_ENTITY_ID: "cover.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("cover.test", "closed", context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_closes_trigger_fully_closed_option(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that closes trigger with fully_closed only fires at position 0."""
    hass.states.async_set("cover.test", "open", {ATTR_CURRENT_POSITION: 100})

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "cover.closes",
                    CONF_TARGET: {CONF_ENTITY_ID: "cover.test"},
                    "fully_closed": True,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # Should not trigger at position 50
    hass.states.async_set("cover.test", "closing", {ATTR_CURRENT_POSITION: 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Should trigger at position 0
    hass.states.async_set("cover.test", "closed", {ATTR_CURRENT_POSITION: 0})
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_stops_trigger_fires_from_opening_to_open(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that stops trigger fires when cover stops from opening."""
    hass.states.async_set("cover.test", "opening")
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "cover.stops",
                    CONF_TARGET: {CONF_ENTITY_ID: "cover.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("cover.test", "open", context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_stops_trigger_fires_from_closing_to_closed(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that stops trigger fires when cover stops from closing."""
    hass.states.async_set("cover.test", "closing")
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "cover.stops",
                    CONF_TARGET: {CONF_ENTITY_ID: "cover.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("cover.test", "closed", context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_stops_trigger_does_not_fire_on_other_changes(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that stops trigger does not fire on other state changes."""
    hass.states.async_set("cover.test", "closed")

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "cover.stops",
                    CONF_TARGET: {CONF_ENTITY_ID: "cover.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # Should not trigger when going from closed to opening
    hass.states.async_set("cover.test", "opening")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Should not trigger when going from open to closing
    hass.states.async_set("cover.test", "open")
    await hass.async_block_till_done()
    hass.states.async_set("cover.test", "closing")
    await hass.async_block_till_done()
    assert len(service_calls) == 0
