"""The tests for the Command line Binary sensor platform."""
from __future__ import annotations

from typing import Any

from pytest import LogCaptureFixture

from homeassistant import setup
from homeassistant.components.binary_sensor import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry


async def setup_test_entity(hass: HomeAssistant, config_dict: dict[str, Any]) -> None:
    """Set up a test command line binary_sensor entity."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"platform": "command_line", "name": "Test", **config_dict}},
    )
    await hass.async_block_till_done()


async def test_setup(hass: HomeAssistant) -> None:
    """Test sensor setup."""
    await setup_test_entity(
        hass,
        {
            "command": "echo 1",
            "payload_on": "1",
            "payload_off": "0",
        },
    )

    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state
    assert entity_state.state == STATE_ON
    assert entity_state.name == "Test"


async def test_template(hass: HomeAssistant) -> None:
    """Test setting the state with a template."""

    await setup_test_entity(
        hass,
        {
            "command": "echo 10",
            "payload_on": "1.0",
            "payload_off": "0",
            "value_template": "{{ value | multiply(0.1) }}",
        },
    )

    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state
    assert entity_state.state == STATE_ON


async def test_sensor_off(hass: HomeAssistant) -> None:
    """Test setting the state with a template."""
    await setup_test_entity(
        hass,
        {
            "command": "echo 0",
            "payload_on": "1",
            "payload_off": "0",
        },
    )
    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state
    assert entity_state.state == STATE_OFF


async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id option and if it only creates one binary sensor per id."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "platform": "command_line",
                    "unique_id": "unique",
                    "command": "echo 0",
                },
                {
                    "platform": "command_line",
                    "unique_id": "not-so-unique-anymore",
                    "command": "echo 1",
                },
                {
                    "platform": "command_line",
                    "unique_id": "not-so-unique-anymore",
                    "command": "echo 2",
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    ent_reg = entity_registry.async_get(hass)

    assert len(ent_reg.entities) == 2
    assert (
        ent_reg.async_get_entity_id("binary_sensor", "command_line", "unique")
        is not None
    )
    assert (
        ent_reg.async_get_entity_id(
            "binary_sensor", "command_line", "not-so-unique-anymore"
        )
        is not None
    )


async def test_return_code(caplog: LogCaptureFixture, hass: HomeAssistant) -> None:
    """Test setting the state with a template."""
    await setup_test_entity(
        hass,
        {
            "command": "exit 33",
        },
    )
    assert "return code 33" in caplog.text
