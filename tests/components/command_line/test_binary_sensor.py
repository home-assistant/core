"""The tests for the Command line Binary sensor platform."""
from __future__ import annotations

import pytest

from homeassistant import setup
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_setup_platform_yaml(hass: HomeAssistant) -> None:
    """Test sensor setup."""
    assert await setup.async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": "command_line",
                "name": "Test",
                "command": "echo 1",
                "payload_on": "1",
                "payload_off": "0",
            }
        },
    )
    await hass.async_block_till_done()

    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state
    assert entity_state.state == STATE_ON
    assert entity_state.name == "Test"


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": {
                "binary_sensors": {
                    "bs_1": {
                        "name": "Test",
                        "command": "echo 1",
                        "payload_on": "1",
                        "payload_off": "0",
                        "command_timeout": 15,
                    }
                }
            }
        }
    ],
)
async def test_setup_integration_yaml(
    hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test sensor setup."""

    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state
    assert entity_state.state == STATE_ON
    assert entity_state.name == "Test"


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": {
                "binary_sensors": {
                    "bs_1": {
                        "name": "Test",
                        "command": "echo 10",
                        "payload_on": "1.0",
                        "payload_off": "0",
                        "value_template": "{{ value | multiply(0.1) }}",
                    }
                }
            }
        }
    ],
)
async def test_template(hass: HomeAssistant, load_yaml_integration: None) -> None:
    """Test setting the state with a template."""

    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state
    assert entity_state.state == STATE_ON


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": {
                "binary_sensors": {
                    "bs_1": {
                        "name": "Test",
                        "command": "echo 0",
                        "payload_on": "1",
                        "payload_off": "0",
                    }
                }
            }
        }
    ],
)
async def test_sensor_off(hass: HomeAssistant, load_yaml_integration: None) -> None:
    """Test setting the state with a template."""

    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state
    assert entity_state.state == STATE_OFF


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": {
                "binary_sensors": {
                    "bs_1": {
                        "unique_id": "unique",
                        "command": "echo 0",
                    },
                    "bs_2": {
                        "unique_id": "not-so-unique-anymore",
                        "command": "echo 1",
                    },
                    "bs_3": {
                        "unique_id": "not-so-unique-anymore",
                        "command": "echo 2",
                    },
                }
            }
        }
    ],
)
async def test_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, load_yaml_integration: None
) -> None:
    """Test unique_id option and if it only creates one binary sensor per id."""

    assert len(hass.states.async_all()) == 2

    assert len(entity_registry.entities) == 2
    assert entity_registry.async_get_entity_id(
        "binary_sensor", "command_line", "unique"
    )
    assert entity_registry.async_get_entity_id(
        "binary_sensor", "command_line", "not-so-unique-anymore"
    )


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": {
                "binary_sensors": {
                    "bs_1": {
                        "command": "exit 33",
                    }
                }
            }
        }
    ],
)
async def test_return_code(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, load_yaml_integration: None
) -> None:
    """Test setting the state with a template."""

    assert "return code 33" in caplog.text
