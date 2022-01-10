"""The tests for the Command line Binary sensor platform."""
from __future__ import annotations

from typing import Callable

import pytest

from homeassistant.components.binary_sensor import DOMAIN as PLATFORM_DOMAIN
from homeassistant.components.command_line import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

ENTITY_NAME = {"name": "Test"}


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command": "echo 1",
                    "payload_on": "1",
                    "payload_off": "0",
                },
            },
        },
    ],
)
async def test_setup(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test sensor setup."""
    await start_ha()

    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state
    assert entity_state.state == STATE_ON
    assert entity_state.name == "Test"


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command": "echo 10",
                    "payload_on": "1.0",
                    "payload_off": "0",
                    "value_template": "{{ value | multiply(0.1) }}",
                },
            },
        },
    ],
)
async def test_template(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test setting the state with a template."""
    await start_ha()

    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state.state == STATE_ON


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command": "echo 0",
                    "payload_on": "1",
                    "payload_off": "0",
                },
            },
        },
    ],
)
async def test_sensor_off(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test setting the state with a template."""
    await start_ha()

    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state.state == STATE_OFF


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: [
                    {
                        "command": "echo 0",
                        "unique_id": "unique",
                    },
                    {
                        "command": "echo 1",
                        "unique_id": "not-so-unique-anymore",
                    },
                    {
                        "command": "echo 2",
                        "unique_id": "not-so-unique-anymore",
                    },
                ],
            },
        },
    ],
)
async def test_unique_id(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test unique_id option and if it only creates one binary sensor per id."""
    await start_ha()

    assert len(hass.states.async_all()) == 2

    ent_reg = entity_registry.async_get(hass)

    assert len(ent_reg.entities) == 2
    assert ent_reg.async_get_entity_id(PLATFORM_DOMAIN, DOMAIN, "unique") is not None
    assert (
        ent_reg.async_get_entity_id(PLATFORM_DOMAIN, DOMAIN, "not-so-unique-anymore")
        is not None
    )
