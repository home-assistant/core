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
    DOMAIN as CLIMATE_DOMAIN,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall
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
    "variables": {"triggering_entity": "{{ trigger.entity_id }}"},
    "action": [
        {"event": "action_event", "event_data": {"what": "{{ triggering_entity}}"}}
    ],
}

SET_HVAC_MODE = {
    "service": "test.automation",
    "data_template": {
        "action": "set_hvac_mode",
        "caller": "{{ this.entity_id }}",
        "hvac_mode": "{{ hvac_mode }}",
    },
}
SET_TEMPERATURE = {
    "service": "test.automation",
    "data_template": {
        "action": "set_temperature",
        "caller": "{{ this.entity_id }}",
        "temperature": "{{ temperature }}",
    },
}
SET_FAN_MODE = {
    "service": "test.automation",
    "data_template": {
        "action": "set_fan_mode",
        "caller": "{{ this.entity_id }}",
        "fan_mode": "{{ fan_mode }}",
    },
}

NAMED_ACTIONS = {
    "name": TEST_OBJECT_ID,
    "set_hvac_mode": SET_HVAC_MODE,
}


async def async_setup_modern_format(
    hass: HomeAssistant, count: int, climate_config: dict[str, Any]
) -> None:
    """Do setup of climate integration via modern format."""
    config = {"template": {"climate": climate_config}}

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(hass, template.DOMAIN, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_trigger_format(
    hass: HomeAssistant, count: int, climate_config: dict[str, Any]
) -> None:
    """Do setup of climate integration via trigger format."""
    config = {"template": {**TEST_STATE_TRIGGER, "climate": climate_config}}

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(hass, template.DOMAIN, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_climate_config(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    climate_config: dict[str, Any],
) -> None:
    """Do setup of climate integration."""
    if style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(hass, count, climate_config)
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(hass, count, climate_config)


@pytest.fixture
async def setup_climate(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    climate_config: dict[str, Any],
) -> None:
    """Do setup of climate integration."""
    await async_setup_climate_config(hass, count, style, climate_config)


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("climate_config", "entity_id"),
    [
        (
            {
                "name": TEST_OBJECT_ID,
                "hvac_mode": "{{ 'heat' }}",
                "hvac_modes": ["heat", "off"],
                "set_hvac_mode": SET_HVAC_MODE,
            },
            TEST_ENTITY_ID,
        ),
    ],
)
@pytest.mark.usefixtures("setup_climate")
async def test_template_state_text(
    hass: HomeAssistant,
    entity_id: str,
) -> None:
    """Test the state of a template climate."""
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
    await hass.async_block_till_done()

    climate_config: dict[str, Any] = {
        "name": TEST_OBJECT_ID,
        "hvac_mode": "{{ states('sensor.mode') }}",
        "hvac_action": "{{ states('sensor.action') }}",
        "current_temperature": "{{ states('sensor.temp') }}",
        "target_temperature": "{{ states('sensor.target') }}",
        "fan_mode": "{{ states('sensor.fan') }}",
        "hvac_modes": ["heat", "cool", "off"],
        "fan_modes": ["low", "high"],
        "set_hvac_mode": SET_HVAC_MODE,
        "set_temperature": SET_TEMPERATURE,
        "set_fan_mode": SET_FAN_MODE,
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
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_actions(
    hass: HomeAssistant, style: ConfigurationStyle, calls: list[ServiceCall]
) -> None:
    """Test actions of a template climate."""
    base = {
        "name": TEST_OBJECT_ID,
        "hvac_modes": ["heat", "off"],
        "set_hvac_mode": SET_HVAC_MODE,
        "set_temperature": SET_TEMPERATURE,
    }

    await async_setup_climate_config(hass, 1, style, base)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(calls) >= 1
    assert calls[-1].data["action"] == "set_hvac_mode"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID
    assert calls[-1].data["hvac_mode"] == HVACMode.HEAT

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert calls[-1].data["action"] == "set_temperature"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID
    assert float(calls[-1].data["temperature"]) == 25.0


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_optimistic_mode(
    hass: HomeAssistant, style: ConfigurationStyle, calls: list[ServiceCall]
) -> None:
    """Test optimistic mode when no state templates are defined."""
    base = {
        "name": TEST_OBJECT_ID,
        "hvac_modes": ["heat", "off"],
        "fan_modes": ["low", "high"],
        "set_hvac_mode": SET_HVAC_MODE,
        "set_fan_mode": SET_FAN_MODE,
    }

    await async_setup_climate_config(hass, 1, style, base)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_fan_mode",
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_FAN_MODE: "high"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_FAN_MODE] == "high"


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_invalid_hvac_mode_logs_and_sets_unknown(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid hvac_mode logs and results in unknown state."""
    hass.states.async_set("sensor.mode", "heat")
    await hass.async_block_till_done()

    base = {
        "name": TEST_OBJECT_ID,
        "hvac_mode": "{{ states('sensor.mode') }}",
        "hvac_modes": ["heat", "off"],
        "set_hvac_mode": SET_HVAC_MODE,
    }

    await async_setup_climate_config(hass, 1, style, base)

    caplog.clear()

    hass.states.async_set("sensor.mode", "dog")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert "Received invalid climate hvac_mode" in caplog.text
    assert "dog" in caplog.text


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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

    base = {
        "name": TEST_OBJECT_ID,
        "hvac_mode": "{{ states('sensor.mode') }}",
        "hvac_action": "{{ states('sensor.action') }}",
        "hvac_modes": ["heat", "off"],
        "set_hvac_mode": SET_HVAC_MODE,
    }

    await async_setup_climate_config(hass, 1, style, base)

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
            "template_type": CLIMATE_DOMAIN,
        },
        title="My Template Climate",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.my_template_climate")
    assert state is not None
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
