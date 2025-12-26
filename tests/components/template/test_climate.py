"""The tests for the Template climate platform."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components import climate, template
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import async_get_flow_preview_state

from tests.common import MockConfigEntry, assert_setup_component
from tests.typing import WebSocketGenerator

TEST_ENTITY_ID = "climate.test_template_climate"


async def test_template_state_text(hass: HomeAssistant) -> None:
    """Test the state text of a template climate."""
    with assert_setup_component(1, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            {
                template.DOMAIN: {
                    climate.DOMAIN: {
                        "hvac_mode": "{{ 'heat' }}",
                        "hvac_modes": ["heat", "off"],
                        "set_hvac_mode": [{"action": "script.turn_on"}],
                    }
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("climate.template_climate")
    assert state.state == HVACMode.HEAT


async def test_template_state_attributes(hass: HomeAssistant) -> None:
    """Test the state attributes of a template climate."""
    hass.states.async_set("sensor.temp", "22")
    hass.states.async_set("sensor.target", "20")
    hass.states.async_set("sensor.mode", "cool")
    hass.states.async_set("sensor.action", "cooling")
    hass.states.async_set("sensor.fan", "high")

    with assert_setup_component(1, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            {
                template.DOMAIN: {
                    climate.DOMAIN: {
                        "hvac_mode": "{{ states('sensor.mode') }}",
                        "hvac_action": "{{ states('sensor.action') }}",
                        "current_temperature": "{{ states('sensor.temp') }}",
                        "target_temperature": "{{ states('sensor.target') }}",
                        "fan_mode": "{{ states('sensor.fan') }}",
                        "hvac_modes": ["heat", "cool", "off"],
                        "fan_modes": ["low", "high"],
                        "set_hvac_mode": [{"action": "script.turn_on"}],
                        "set_temperature": [{"action": "script.turn_on"}],
                        "set_fan_mode": [{"action": "script.turn_on"}],
                    }
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("climate.template_climate")
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.0
    assert state.attributes[ATTR_TEMPERATURE] == 20.0
    assert state.attributes[ATTR_FAN_MODE] == "high"
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING

    hass.states.async_set("sensor.temp", "25")
    hass.states.async_set("sensor.action", "idle")
    await hass.async_block_till_done()

    state = hass.states.get("climate.template_climate")
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 25.0
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_actions(hass: HomeAssistant) -> None:
    """Test actions of the template climate."""
    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"test_hvac": {}}}
    )
    assert await async_setup_component(
        hass,
        "input_number",
        {"input_number": {"test_temp": {"min": 0, "max": 100, "step": 1}}},
    )

    with assert_setup_component(1, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            {
                template.DOMAIN: {
                    climate.DOMAIN: {
                        "hvac_modes": ["heat", "off"],
                        "set_hvac_mode": [
                            {
                                "action": "input_boolean.turn_on",
                                "target": {"entity_id": "input_boolean.test_hvac"},
                            }
                        ],
                        "set_temperature": [
                            {
                                "action": "input_number.set_value",
                                "target": {"entity_id": "input_number.test_temp"},
                                "data": {"value": "{{ temperature }}"},
                            }
                        ],
                    }
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    await hass.services.async_call(
        climate.DOMAIN,
        "set_hvac_mode",
        {ATTR_ENTITY_ID: "climate.template_climate", ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    assert hass.states.get("input_boolean.test_hvac").state == "on"

    await hass.services.async_call(
        climate.DOMAIN,
        "set_temperature",
        {ATTR_ENTITY_ID: "climate.template_climate", ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    assert hass.states.get("input_number.test_temp").state == "25.0"


async def test_optimistic_mode(hass: HomeAssistant) -> None:
    """Test optimistic mode when no state template is defined."""
    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"test": {}}}
    )

    with assert_setup_component(1, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            {
                template.DOMAIN: {
                    climate.DOMAIN: {
                        "hvac_modes": ["heat", "off"],
                        "fan_modes": ["low", "high"],
                        "set_hvac_mode": [
                            {
                                "action": "input_boolean.turn_on",
                                "target": {"entity_id": "input_boolean.test"},
                            }
                        ],
                        "set_fan_mode": [
                            {
                                "action": "input_boolean.turn_on",
                                "target": {"entity_id": "input_boolean.test"},
                            }
                        ],
                    }
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    entity_id = "climate.template_climate"
    state = hass.states.get(entity_id)

    await hass.services.async_call(
        climate.DOMAIN,
        "set_hvac_mode",
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.HEAT

    await hass.services.async_call(
        climate.DOMAIN,
        "set_fan_mode",
        {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: "high"},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_FAN_MODE] == "high"


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests creating a climate from a config entry."""

    hass.states.async_set(
        "sensor.test_temp",
        "21.5",
        {},
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My Template Climate",
            "current_temperature": "{{ states('sensor.test_temp') }}",
            "hvac_mode": "heat",
            "hvac_modes": ["heat", "off"],
            "set_hvac_mode": [],
            "template_type": climate.DOMAIN,
        },
        title="My Template Climate",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.my_template_climate")
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.5

    assert state == snapshot


async def test_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""

    hass.states.async_set("sensor.temp", "18")

    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        climate.DOMAIN,
        {
            "name": "Preview Climate",
            "hvac_modes": ["cool", "off"],
            "hvac_mode": "cool",
            "current_temperature": "{{ states('sensor.temp') }}",
            "set_hvac_mode": [],
        },
    )

    assert state["state"] == "cool"
    assert state["attributes"]["current_temperature"] == 18.0
