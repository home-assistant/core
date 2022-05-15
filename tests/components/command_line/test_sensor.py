"""The tests for the Command line sensor platform."""
from __future__ import annotations

from unittest.mock import patch

from pytest import LogCaptureFixture

from homeassistant import setup
from homeassistant.components.command_line.const import CONF_COMMAND_TIMEOUT
from homeassistant.components.sensor import DOMAIN
from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from . import setup_test_entities


async def test_setup(hass: HomeAssistant) -> None:
    """Test sensor setup."""
    await setup_test_entities(
        hass,
        {
            CONF_PLATFORM: "sensor",
            CONF_NAME: "Test",
            "command": "echo 5",
            "unit_of_measurement": "in",
            CONF_COMMAND_TIMEOUT: 15,
        },
    )
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == "5"
    assert entity_state.name == "Test"
    assert entity_state.attributes["unit_of_measurement"] == "in"


async def test_template(hass: HomeAssistant) -> None:
    """Test command sensor with template."""
    await setup_test_entities(
        hass,
        {
            CONF_PLATFORM: "sensor",
            CONF_NAME: "Test",
            "command": "echo 50",
            "unit_of_measurement": "in",
            "value_template": "{{ value | multiply(0.1) }}",
            CONF_COMMAND_TIMEOUT: 15,
        },
    )
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert float(entity_state.state) == 5


async def test_template_render(hass: HomeAssistant) -> None:
    """Ensure command with templates get rendered properly."""

    await setup_test_entities(
        hass,
        {
            CONF_PLATFORM: "sensor",
            CONF_NAME: "Test",
            "command": "echo {{ states.sensor.template_sensor.state }}",
            CONF_COMMAND_TIMEOUT: 15,
        },
    )
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == "template_value"


async def test_template_render_with_quote(hass: HomeAssistant) -> None:
    """Ensure command with templates and quotes get rendered properly."""

    with patch(
        "homeassistant.components.command_line.util.subprocess.check_output",
        return_value=b"Works\n",
    ) as check_output:
        await setup_test_entities(
            hass,
            {
                CONF_PLATFORM: "sensor",
                CONF_NAME: "Test",
                "command": 'echo "{{ states.sensor.template_sensor.state }}" "3 4"',
                CONF_COMMAND_TIMEOUT: 15,
            },
        )

        check_output.assert_called_once_with(
            'echo "template_value" "3 4"',
            shell=True,  # nosec # shell by design
            timeout=15,
        )


async def test_bad_template_render(
    caplog: LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test rendering a broken template."""

    await setup_test_entities(
        hass,
        {
            CONF_PLATFORM: "sensor",
            CONF_NAME: "Test",
            "command": "echo {{ this template doesn't parse",
            CONF_COMMAND_TIMEOUT: 15,
        },
    )

    assert "Error rendering command template" in caplog.text


async def test_bad_command(hass: HomeAssistant) -> None:
    """Test bad command."""
    await setup_test_entities(
        hass,
        {
            CONF_PLATFORM: "sensor",
            CONF_NAME: "Test",
            "command": "asdfasdf",
            CONF_COMMAND_TIMEOUT: 15,
        },
    )
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == "unknown"


async def test_return_code(caplog: LogCaptureFixture, hass: HomeAssistant) -> None:
    """Test that an error return code is logged."""
    await setup_test_entities(
        hass,
        {
            "command": "exit 33",
        },
    )
    assert "return code 33" in caplog.text


async def test_update_with_json_attrs(hass: HomeAssistant) -> None:
    """Test attributes get extracted from a JSON result."""
    await setup_test_entities(
        hass,
        {
            CONF_PLATFORM: "sensor",
            CONF_NAME: "Test",
            "command": 'echo { \\"key\\": \\"some_json_value\\", \\"another_key\\":\
                \\"another_json_value\\", \\"key_three\\": \\"value_three\\" }',
            "json_attributes": ["key", "another_key", "key_three"],
            CONF_COMMAND_TIMEOUT: 15,
        },
    )
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.attributes["key"] == "some_json_value"
    assert entity_state.attributes["another_key"] == "another_json_value"
    assert entity_state.attributes["key_three"] == "value_three"


async def test_update_with_json_attrs_no_data(
    caplog: LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test attributes when no JSON result fetched."""

    await setup_test_entities(
        hass,
        {
            CONF_PLATFORM: "sensor",
            CONF_NAME: "Test",
            "command": "echo",
            "json_attributes": ["key"],
            CONF_COMMAND_TIMEOUT: 15,
        },
    )
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert "key" not in entity_state.attributes
    assert "Empty reply found when expecting JSON data" in caplog.text


async def test_update_with_json_attrs_not_dict(
    caplog: LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test attributes when the return value not a dict."""

    await setup_test_entities(
        hass,
        {
            CONF_PLATFORM: "sensor",
            CONF_NAME: "Test",
            "command": "echo [1, 2, 3]",
            "json_attributes": ["key"],
            CONF_COMMAND_TIMEOUT: 15,
        },
    )
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert "key" not in entity_state.attributes
    assert "JSON result was not a dictionary" in caplog.text


async def test_update_with_json_attrs_bad_json(
    caplog: LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test attributes when the return value is invalid JSON."""

    await setup_test_entities(
        hass,
        {
            CONF_PLATFORM: "sensor",
            CONF_NAME: "Test",
            "command": "echo This is text rather than JSON data.",
            "json_attributes": ["key"],
            CONF_COMMAND_TIMEOUT: 15,
        },
    )
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert "key" not in entity_state.attributes
    assert "Unable to parse output as JSON" in caplog.text


async def test_update_with_missing_json_attrs(
    caplog: LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test attributes when an expected key is missing."""

    await setup_test_entities(
        hass,
        {
            CONF_PLATFORM: "sensor",
            CONF_NAME: "Test",
            "command": 'echo { \\"key\\": \\"some_json_value\\", \\"another_key\\":\
                \\"another_json_value\\", \\"key_three\\": \\"value_three\\" }',
            "json_attributes": ["key", "another_key", "key_three", "missing_key"],
            CONF_COMMAND_TIMEOUT: 15,
        },
    )
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.attributes["key"] == "some_json_value"
    assert entity_state.attributes["another_key"] == "another_json_value"
    assert entity_state.attributes["key_three"] == "value_three"
    assert "missing_key" not in entity_state.attributes


async def test_update_with_unnecessary_json_attrs(
    caplog: LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test attributes when an expected key is missing."""

    await setup_test_entities(
        hass,
        {
            CONF_PLATFORM: "sensor",
            CONF_NAME: "Test",
            "command": 'echo { \\"key\\": \\"some_json_value\\", \\"another_key\\":\
                \\"another_json_value\\", \\"key_three\\": \\"value_three\\" }',
            "json_attributes": ["key", "another_key"],
            CONF_COMMAND_TIMEOUT: 15,
        },
    )
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.attributes["key"] == "some_json_value"
    assert entity_state.attributes["another_key"] == "another_json_value"
    assert "key_three" not in entity_state.attributes


async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id option and if it only creates one sensor per id."""
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

    assert len(hass.states.async_all()) == 3

    ent_reg = entity_registry.async_get(hass)

    assert len(ent_reg.entities) == 2
    assert ent_reg.async_get_entity_id("sensor", "command_line", "unique") is not None
    assert (
        ent_reg.async_get_entity_id("sensor", "command_line", "not-so-unique-anymore")
        is not None
    )
