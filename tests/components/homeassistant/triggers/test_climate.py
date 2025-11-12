"""The tests for the Climate automation."""

import pytest

from homeassistant.components import automation
from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TARGET,
)
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.common import mock_component


@pytest.fixture(autouse=True)
def setup_comp(hass: HomeAssistant) -> None:
    """Initialize components."""
    mock_component(hass, "group")


async def test_turns_on_trigger_fires_when_turning_on(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that turns_on trigger fires when climate turns on."""
    hass.states.async_set("climate.test", "off")
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "climate.turns_on",
                    CONF_TARGET: {CONF_ENTITY_ID: "climate.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("climate.test", "heat", context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_turns_on_trigger_does_not_fire_when_already_on(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that turns_on trigger does not fire when already on."""
    hass.states.async_set("climate.test", "heat")

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "climate.turns_on",
                    CONF_TARGET: {CONF_ENTITY_ID: "climate.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("climate.test", "cool")
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_turns_off_trigger_fires_when_turning_off(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that turns_off trigger fires when climate turns off."""
    hass.states.async_set("climate.test", "heat")
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "climate.turns_off",
                    CONF_TARGET: {CONF_ENTITY_ID: "climate.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("climate.test", "off", context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_mode_changed_trigger_fires_on_mode_change(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that mode_changed trigger fires when mode changes."""
    hass.states.async_set("climate.test", "heat")
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "climate.mode_changed",
                    CONF_TARGET: {CONF_ENTITY_ID: "climate.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("climate.test", "cool", context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_mode_changed_trigger_filters_by_hvac_mode(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that mode_changed trigger filters by hvac_mode."""
    hass.states.async_set("climate.test", "off")

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "climate.mode_changed",
                    CONF_TARGET: {CONF_ENTITY_ID: "climate.test"},
                    "hvac_mode": ["heat", "cool"],
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # Should trigger for heat
    hass.states.async_set("climate.test", "heat")
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    # Should trigger for cool
    hass.states.async_set("climate.test", "cool")
    await hass.async_block_till_done()
    assert len(service_calls) == 2

    # Should not trigger for auto
    hass.states.async_set("climate.test", "auto")
    await hass.async_block_till_done()
    assert len(service_calls) == 2


async def test_cooling_trigger_fires_when_cooling_starts(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that cooling trigger fires when climate starts cooling."""
    hass.states.async_set("climate.test", "cool", {ATTR_HVAC_ACTION: "idle"})
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "climate.cooling",
                    CONF_TARGET: {CONF_ENTITY_ID: "climate.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(
        "climate.test", "cool", {ATTR_HVAC_ACTION: "cooling"}, context=context
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_heating_trigger_fires_when_heating_starts(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that heating trigger fires when climate starts heating."""
    hass.states.async_set("climate.test", "heat", {ATTR_HVAC_ACTION: "idle"})
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "climate.heating",
                    CONF_TARGET: {CONF_ENTITY_ID: "climate.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(
        "climate.test", "heat", {ATTR_HVAC_ACTION: "heating"}, context=context
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_drying_trigger_fires_when_drying_starts(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that drying trigger fires when climate starts drying."""
    hass.states.async_set("climate.test", "dry", {ATTR_HVAC_ACTION: "idle"})
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "climate.drying",
                    CONF_TARGET: {CONF_ENTITY_ID: "climate.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(
        "climate.test", "dry", {ATTR_HVAC_ACTION: "drying"}, context=context
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_target_temperature_changed_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that target_temperature_changed trigger fires."""
    hass.states.async_set("climate.test", "heat", {ATTR_TEMPERATURE: 20})
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "climate.target_temperature_changed",
                    CONF_TARGET: {CONF_ENTITY_ID: "climate.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(
        "climate.test", "heat", {ATTR_TEMPERATURE: 22}, context=context
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_target_temperature_changed_trigger_with_above(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that target_temperature_changed trigger filters by above threshold."""
    hass.states.async_set("climate.test", "heat", {ATTR_TEMPERATURE: 20})

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "climate.target_temperature_changed",
                    CONF_TARGET: {CONF_ENTITY_ID: "climate.test"},
                    "above": 22,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # Should not trigger at 21
    hass.states.async_set("climate.test", "heat", {ATTR_TEMPERATURE: 21})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Should trigger at 23
    hass.states.async_set("climate.test", "heat", {ATTR_TEMPERATURE: 23})
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_current_temperature_changed_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that current_temperature_changed trigger fires."""
    hass.states.async_set("climate.test", "heat", {ATTR_CURRENT_TEMPERATURE: 20})
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "climate.current_temperature_changed",
                    CONF_TARGET: {CONF_ENTITY_ID: "climate.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(
        "climate.test", "heat", {ATTR_CURRENT_TEMPERATURE: 21}, context=context
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_target_humidity_changed_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that target_humidity_changed trigger fires."""
    hass.states.async_set("climate.test", "dry", {ATTR_HUMIDITY: 50})
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "climate.target_humidity_changed",
                    CONF_TARGET: {CONF_ENTITY_ID: "climate.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("climate.test", "dry", {ATTR_HUMIDITY: 60}, context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_current_humidity_changed_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that current_humidity_changed trigger fires."""
    hass.states.async_set("climate.test", "dry", {ATTR_CURRENT_HUMIDITY: 50})
    context = Context()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "climate.current_humidity_changed",
                    CONF_TARGET: {CONF_ENTITY_ID: "climate.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(
        "climate.test", "dry", {ATTR_CURRENT_HUMIDITY: 55}, context=context
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_does_not_fire_on_unavailable(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that trigger does not fire when state becomes unavailable."""
    hass.states.async_set("climate.test", "heat")

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "climate.turns_off",
                    CONF_TARGET: {CONF_ENTITY_ID: "climate.test"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("climate.test", "unavailable")
    await hass.async_block_till_done()
    assert len(service_calls) == 0
