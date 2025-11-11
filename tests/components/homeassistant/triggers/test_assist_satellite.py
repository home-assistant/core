"""The tests for the Assist satellite automation."""

import pytest

from homeassistant.components import automation
from homeassistant.const import CONF_ENTITY_ID, CONF_PLATFORM, CONF_TARGET
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.common import mock_component


@pytest.fixture(autouse=True)
def setup_comp(hass: HomeAssistant) -> None:
    """Initialize components."""
    mock_component(hass, "group")


@pytest.mark.parametrize(
    ("trigger", "state"),
    [
        ("assist_satellite.listening", "listening"),
        ("assist_satellite.processing", "processing"),
        ("assist_satellite.responding", "responding"),
        ("assist_satellite.idle", "idle"),
    ],
)
async def test_trigger_fires_on_state_change(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger: str,
    state: str,
) -> None:
    """Test that the trigger fires when satellite changes to the specified state."""
    hass.states.async_set("assist_satellite.satellite_1", "idle")
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: trigger,
                    CONF_TARGET: {CONF_ENTITY_ID: "assist_satellite.satellite_1"},
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {"id": "{{ trigger.id}}"},
                },
            }
        },
    )

    hass.states.async_set("assist_satellite.satellite_1", state, context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_listening_does_not_fire_on_other_states(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that listening trigger does not fire on other states."""
    hass.states.async_set("assist_satellite.satellite_1", "idle")

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "assist_satellite.listening",
                    CONF_TARGET: {CONF_ENTITY_ID: "assist_satellite.satellite_1"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("assist_satellite.satellite_1", "processing")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set("assist_satellite.satellite_1", "responding")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set("assist_satellite.satellite_1", "idle")
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_does_not_fire_on_unavailable(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that trigger does not fire when state becomes unavailable."""
    hass.states.async_set("assist_satellite.satellite_1", "idle")

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "assist_satellite.listening",
                    CONF_TARGET: {CONF_ENTITY_ID: "assist_satellite.satellite_1"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("assist_satellite.satellite_1", "unavailable")
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_fires_with_multiple_entities(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the firing with multiple entities."""
    hass.states.async_set("assist_satellite.satellite_1", "idle")
    hass.states.async_set("assist_satellite.satellite_2", "idle")

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "assist_satellite.listening",
                    CONF_TARGET: {
                        CONF_ENTITY_ID: [
                            "assist_satellite.satellite_1",
                            "assist_satellite.satellite_2",
                        ]
                    },
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("assist_satellite.satellite_1", "listening")
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    hass.states.async_set("assist_satellite.satellite_2", "listening")
    await hass.async_block_till_done()
    assert len(service_calls) == 2


async def test_trigger_data_available(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that trigger data is available in action."""
    hass.states.async_set("assist_satellite.satellite_1", "idle")

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "assist_satellite.listening",
                    CONF_TARGET: {CONF_ENTITY_ID: "assist_satellite.satellite_1"},
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

    hass.states.async_set("assist_satellite.satellite_1", "listening")
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["entity_id"] == "assist_satellite.satellite_1"
    assert service_calls[0].data["from_state"] == "idle"
    assert service_calls[0].data["to_state"] == "listening"


async def test_idle_trigger_fires_when_returning_to_idle(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that idle trigger fires when satellite returns to idle."""
    hass.states.async_set("assist_satellite.satellite_1", "listening")
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "assist_satellite.idle",
                    CONF_TARGET: {CONF_ENTITY_ID: "assist_satellite.satellite_1"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # Go to processing state first
    hass.states.async_set("assist_satellite.satellite_1", "processing")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Go back to idle
    hass.states.async_set("assist_satellite.satellite_1", "idle", context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id
