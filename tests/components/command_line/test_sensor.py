"""The tests for the Command line sensor platform."""
from __future__ import annotations

from typing import Any, Callable
from unittest.mock import patch

import pytest

from homeassistant.components.command_line import DOMAIN
from homeassistant.components.sensor import DOMAIN as PLATFORM_DOMAIN
from homeassistant.components.template import DOMAIN as TEMPLATE_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

TEMPLATE_SENSOR_CONFIG = {
    TEMPLATE_DOMAIN: {
        PLATFORM_DOMAIN: {
            "name": "template_sensor",
            "state": "template_value",
        },
    },
}

ENTITY_NAME = {"name": "Test"}


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command": "echo 5",
                    "unit_of_measurement": "in",
                },
            },
        },
    ],
)
async def test_setup(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test sensor setup."""
    await start_ha()
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == "5"
    assert entity_state.name == "Test"
    assert entity_state.attributes["unit_of_measurement"] == "in"


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command": "echo 50",
                    "value_template": "{{ value | multiply(0.1) }}",
                },
            },
        },
    ],
)
async def test_template(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test command sensor with template."""
    await start_ha()
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert float(entity_state.state) == 5


@pytest.mark.parametrize("domains", [[(DOMAIN, 1), (TEMPLATE_DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            **TEMPLATE_SENSOR_CONFIG,
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command": "echo {{ states.sensor.template_sensor.state }}",
                },
            },
        },
    ],
)
async def test_template_render(hass: HomeAssistant, start_ha: Callable) -> None:
    """Ensure command with templates get rendered properly."""
    await start_ha()
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == "template_value"


@pytest.mark.parametrize("domains", [[(DOMAIN, 1), (TEMPLATE_DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            **TEMPLATE_SENSOR_CONFIG,
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command": 'echo "{{ states.sensor.template_sensor.state }}" "3 4"',
                },
            },
        },
    ],
)
async def test_template_render_with_quote(
    hass: HomeAssistant, start_ha: Callable
) -> None:
    """Ensure command with templates and quotes get rendered properly."""
    with patch(
        "homeassistant.components.command_line.subprocess.check_output",
        return_value=b"Works\n",
    ) as check_output:
        await start_ha()

        check_output.assert_called_once_with(
            'echo "template_value" "3 4"',
            shell=True,  # nosec # shell by design
            timeout=15,
        )


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command": "echo {{ this template doesn't parse",
                },
            },
        },
    ],
)
async def test_bad_template_render(
    caplog: Any, hass: HomeAssistant, start_ha: Callable
) -> None:
    """Test rendering a broken template."""
    await start_ha()
    assert "Error rendering command template" in caplog.text


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command": "asdfasdf",
                },
            },
        },
    ],
)
async def test_bad_command(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test bad command."""
    await start_ha()
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == "unknown"


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command": 'echo { \\"key\\": \\"some_json_value\\", \\"another_key\\":\
                        \\"another_json_value\\", \\"key_three\\": \\"value_three\\" }',
                    "json_attributes": ["key", "another_key", "key_three"],
                },
            },
        },
    ],
)
async def test_update_with_json_attrs(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test attributes get extracted from a JSON result."""
    await start_ha()
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.attributes["key"] == "some_json_value"
    assert entity_state.attributes["another_key"] == "another_json_value"
    assert entity_state.attributes["key_three"] == "value_three"


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command": "echo",
                    "json_attributes": ["key"],
                },
            },
        },
    ],
)
async def test_update_with_json_attrs_no_data(caplog, hass: HomeAssistant, start_ha: Callable) -> None:  # type: ignore[no-untyped-def]
    """Test attributes when no JSON result fetched."""
    await start_ha()
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert "key" not in entity_state.attributes
    assert "Empty reply found when expecting JSON data" in caplog.text


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command": "echo [1, 2, 3]",
                    "json_attributes": ["key"],
                },
            },
        },
    ],
)
async def test_update_with_json_attrs_not_dict(caplog, hass: HomeAssistant, start_ha: Callable) -> None:  # type: ignore[no-untyped-def]
    """Test attributes when the return value not a dict."""
    await start_ha()
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert "key" not in entity_state.attributes
    assert "JSON result was not a dictionary" in caplog.text


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command": "echo This is text rather than JSON data.",
                    "json_attributes": ["key"],
                },
            },
        },
    ],
)
async def test_update_with_json_attrs_bad_json(caplog, hass: HomeAssistant, start_ha: Callable) -> None:  # type: ignore[no-untyped-def]
    """Test attributes when the return value is invalid JSON."""
    await start_ha()
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert "key" not in entity_state.attributes
    assert "Unable to parse output as JSON" in caplog.text


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command": 'echo { \\"key\\": \\"some_json_value\\", \\"another_key\\":\
                        \\"another_json_value\\", \\"key_three\\": \\"value_three\\" }',
                    "json_attributes": [
                        "key",
                        "another_key",
                        "key_three",
                        "missing_key",
                    ],
                },
            },
        },
    ],
)
async def test_update_with_missing_json_attrs(caplog, hass: HomeAssistant, start_ha: Callable) -> None:  # type: ignore[no-untyped-def]
    """Test attributes when an expected key is missing."""
    await start_ha()
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.attributes["key"] == "some_json_value"
    assert entity_state.attributes["another_key"] == "another_json_value"
    assert entity_state.attributes["key_three"] == "value_three"
    assert "missing_key" not in entity_state.attributes


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command": 'echo { \\"key\\": \\"some_json_value\\", \\"another_key\\":\
                        \\"another_json_value\\", \\"key_three\\": \\"value_three\\" }',
                    "json_attributes": ["key", "another_key"],
                },
            },
        },
    ],
)
async def test_update_with_unnecessary_json_attrs(caplog, hass: HomeAssistant, start_ha: Callable) -> None:  # type: ignore[no-untyped-def]
    """Test attributes when an expected key is missing."""
    await start_ha()
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.attributes["key"] == "some_json_value"
    assert entity_state.attributes["another_key"] == "another_json_value"
    assert "key_three" not in entity_state.attributes


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
    """Test unique_id option and if it only creates one sensor per id."""
    await start_ha()

    assert len(hass.states.async_all()) == 2

    ent_reg = entity_registry.async_get(hass)

    assert len(ent_reg.entities) == 2
    assert ent_reg.async_get_entity_id(PLATFORM_DOMAIN, DOMAIN, "unique") is not None
    assert (
        ent_reg.async_get_entity_id(PLATFORM_DOMAIN, DOMAIN, "not-so-unique-anymore")
        is not None
    )
