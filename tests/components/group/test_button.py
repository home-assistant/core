"""The tests for the group button platform."""

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.group import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util


async def test_default_state(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test button group default state."""
    hass.states.async_set("button.notify_light", "2021-01-01T23:59:59.123+00:00")
    await async_setup_component(
        hass,
        BUTTON_DOMAIN,
        {
            BUTTON_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["button.notify_light", "button.self_destruct"],
                "name": "Button group",
                "unique_id": "unique_identifier",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("button.button_group")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ENTITY_ID) == [
        "button.notify_light",
        "button.self_destruct",
    ]

    entry = entity_registry.async_get("button.button_group")
    assert entry
    assert entry.unique_id == "unique_identifier"


async def test_state_reporting(hass: HomeAssistant) -> None:
    """Test the state reporting.

    The group state is unavailable if all group members are unavailable.
    Otherwise, the group state represents the last time the grouped button was pressed.
    """
    await async_setup_component(
        hass,
        BUTTON_DOMAIN,
        {
            BUTTON_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["button.test1", "button.test2"],
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Initial state with no group member in the state machine -> unavailable
    assert hass.states.get("button.button_group").state == STATE_UNAVAILABLE

    # All group members unavailable -> unavailable
    hass.states.async_set("button.test1", STATE_UNAVAILABLE)
    hass.states.async_set("button.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("button.button_group").state == STATE_UNAVAILABLE

    # All group members available, but no group member pressed -> unknown
    hass.states.async_set("button.test1", "2021-01-01T23:59:59.123+00:00")
    hass.states.async_set("button.test2", "2022-02-02T23:59:59.123+00:00")
    await hass.async_block_till_done()
    assert hass.states.get("button.button_group").state == STATE_UNKNOWN


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_service_calls(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test service calls."""
    await async_setup_component(
        hass,
        BUTTON_DOMAIN,
        {
            BUTTON_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": [
                        "button.push",
                        "button.self_destruct",
                    ],
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get("button.button_group").state == STATE_UNKNOWN
    assert hass.states.get("button.push").state == STATE_UNKNOWN

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    freezer.move_to(now)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.button_group"},
        blocking=True,
    )

    assert hass.states.get("button.button_group").state == now.isoformat()
    assert hass.states.get("button.push").state == now.isoformat()
