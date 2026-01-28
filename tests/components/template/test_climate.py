"""The tests for the Template climate platform."""

from __future__ import annotations

from typing import Any

import pytest
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
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import ConfigurationStyle, async_get_flow_preview_state

from tests.common import MockConfigEntry, assert_setup_component
from tests.typing import WebSocketGenerator

TEST_OBJECT_ID = "test_template_climate"
TEST_ENTITY_ID = f"climate.{TEST_OBJECT_ID}"

TEST_STATE_TRIGGER = {
    "trigger": {
        "trigger": "state",
        "entity_id": [
            "sensor.temp",
            "sensor.target",
            "sensor.mode",
            "sensor.action",
            "sensor.fan",
        ],
    },
    "action": [{"event": "action_event"}],
}


async def async_setup_modern_format(
    hass: HomeAssistant, expected: int, climate_config: dict[str, Any]
) -> None:
    """Set up climate via modern YAML format."""
    config = {"template": {"climate": climate_config}}

    with assert_setup_component(expected, template.DOMAIN):
        assert await async_setup_component(hass, template.DOMAIN, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_trigger_format(
    hass: HomeAssistant, expected: int, climate_config: dict[str, Any]
) -> None:
    """Set up climate via trigger-based YAML format."""
    config = {"template": {**TEST_STATE_TRIGGER, "climate": climate_config}}

    with assert_setup_component(expected, template.DOMAIN):
        assert await async_setup_component(hass, template.DOMAIN, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_climate_config(
    hass: HomeAssistant,
    expected: int,
    style: ConfigurationStyle,
    climate_config: dict[str, Any],
) -> None:
    """Set up climate for the requested configuration style."""
    if style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(hass, expected, climate_config)
        return
    await async_setup_modern_format(hass, expected, climate_config)


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_template_state_text(
    hass: HomeAssistant, style: ConfigurationStyle
) -> None:
    """Test the state of a template climate."""
    climate_config: dict[str, Any] = {
        "name": TEST_OBJECT_ID,
        "hvac_mode": "{{ 'heat' }}",
        "hvac_modes": ["heat", "off"],
        "set_hvac_mode": [{"action": "script.turn_on"}],
    }

    await async_setup_climate_config(hass, 1, style, climate_config)

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_template_state_attributes(
    hass: HomeAssistant, style: ConfigurationStyle
) -> None:
    """Test state attributes of a template climate."""
    hass.states.async_set("sensor.temp", "22")
    hass.states.async_set("sensor.target", "20")
    hass.states.async_set("sensor.mode", "cool")
    hass.states.async_set("sensor.action", "cooling")
    hass.states.async_set("sensor.fan", "high")

    climate_config: dict[str, Any] = {
        "name": TEST_OBJECT_ID,
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

    await async_setup_climate_config(hass, 1, style, climate_config)

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.0
    assert state.attributes[ATTR_TEMPERATURE] == 20.0
    assert state.attributes[ATTR_FAN_MODE] == "high"
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING

    hass.states.async_set("sensor.temp", "25")
    hass.states.async_set("sensor.action", "idle")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 25.0
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_actions(hass: HomeAssistant, style: ConfigurationStyle) -> None:
    """Test actions of a template climate."""
    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"test_hvac": {}}}
    )
    assert await async_setup_component(
        hass,
        "input_number",
        {"input_number": {"test_temp": {"min": 0, "max": 100, "step": 1}}},
    )

    climate_config: dict[str, Any] = {
        "name": TEST_OBJECT_ID,
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

    await async_setup_climate_config(hass, 1, style, climate_config)

    await hass.services.async_call(
        climate.DOMAIN,
        "set_hvac_mode",
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    assert hass.states.get("input_boolean.test_hvac").state == "on"

    await hass.services.async_call(
        climate.DOMAIN,
        "set_temperature",
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    assert hass.states.get("input_number.test_temp").state == "25.0"


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_optimistic_mode(hass: HomeAssistant, style: ConfigurationStyle) -> None:
    """Test optimistic mode when no state templates are defined."""
    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"test": {}}}
    )

    climate_config: dict[str, Any] = {
        "name": TEST_OBJECT_ID,
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

    await async_setup_climate_config(hass, 1, style, climate_config)

    await hass.services.async_call(
        climate.DOMAIN,
        "set_hvac_mode",
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT

    await hass.services.async_call(
        climate.DOMAIN,
        "set_fan_mode",
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_FAN_MODE: "high"},
        blocking=True,
    )
    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_FAN_MODE] == "high"


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_invalid_hvac_mode_logs_and_sets_unknown(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid hvac_mode logs and results in unknown state."""
    hass.states.async_set("sensor.mode", "heat")
    await hass.async_block_till_done()

    climate_config: dict[str, Any] = {
        "name": TEST_OBJECT_ID,
        "hvac_mode": "{{ states('sensor.mode') }}",
        "hvac_modes": ["heat", "off"],
        "set_hvac_mode": [{"action": "script.turn_on"}],
    }

    await async_setup_climate_config(hass, 1, style, climate_config)

    caplog.clear()

    hass.states.async_set("sensor.mode", "dog")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert "Received invalid climate hvac_mode" in caplog.text
    assert "dog" in caplog.text


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_invalid_hvac_action_logs_and_clears_attribute(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid hvac_action logs and clears attribute."""
    hass.states.async_set("sensor.mode", "heat")
    hass.states.async_set("sensor.action", "idle")
    await hass.async_block_till_done()

    climate_config: dict[str, Any] = {
        "name": TEST_OBJECT_ID,
        "hvac_mode": "{{ states('sensor.mode') }}",
        "hvac_action": "{{ states('sensor.action') }}",
        "hvac_modes": ["heat", "off"],
        "set_hvac_mode": [{"action": "script.turn_on"}],
    }

    await async_setup_climate_config(hass, 1, style, climate_config)

    caplog.clear()

    hass.states.async_set("sensor.action", "barking")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_HVAC_ACTION) is None
    assert "Received invalid climate hvac_action" in caplog.text
    assert "barking" in caplog.text


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating a climate from a config entry."""
    hass.states.async_set("sensor.test_temp", "21.5", {})
    await hass.async_block_till_done()

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
    await hass.async_block_till_done()

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
